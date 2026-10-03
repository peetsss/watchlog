"""Transactional lobby game services.

All state transitions live here, never in websocket consumers or template
views. Network calls (Ollama/TMDB) must happen outside these transactions;
callers refill/queue first, then invoke ballot resolution. Channel messages
are scheduled with `transaction.on_commit` via `lobby.live`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from groups.models import Group, GroupMovie
from movies.models import Movie
from movies.services import add_to_personal_watchlist, mark_personally_watched

from . import rules
from .live import broadcast_session
from .models import (
    LobbyBallot,
    LobbyCard,
    LobbyParticipant,
    LobbySession,
    WatchlistOffer,
    WatchlistOfferResponse,
)
from .quiz import select_quiz_snapshot, validate_quiz_answers

User = get_user_model()

CardOutcome = Literal["pending", "matched", "watched", "vetoed", "exhausted"]


@dataclass(frozen=True, slots=True)
class BallotResult:
    outcome: CardOutcome
    session: LobbySession
    card: LobbyCard
    submitted_count: int
    participant_count: int
    offer_id: int | None = None


class LobbyError(ValueError):
    """Domain validation failure (membership, state, idempotency-safe)."""


def _require_group_member(group: Group, user) -> None:
    if not group.members.filter(pk=user.pk).exists():
        raise LobbyError("only group members may join this lobby")


def _get_participant(session: LobbySession, user) -> LobbyParticipant:
    try:
        return LobbyParticipant.objects.get(session=session, user=user)
    except LobbyParticipant.DoesNotExist:
        raise LobbyError("caller is not a participant in this session") from None


def _emit(session_id: UUID, event_type: str, **payload) -> None:
    transaction.on_commit(lambda: broadcast_session(session_id, {"type": event_type, **payload}))


def create_session(group: Group, host) -> LobbySession:
    """Create a waiting session with a fresh shared quiz snapshot."""
    _require_group_member(group, host)
    if LobbySession.objects.filter(group=group, status__in=["waiting", "active"]).exists():
        raise LobbyError("this group already has an open lobby session")
    session = LobbySession.objects.create(
        group=group,
        host=host,
        rules_version=rules.RULES_VERSION,
        quiz_version=rules.QUIZ_VERSION,
        quiz_snapshot=select_quiz_snapshot(),
    )
    # Deterministic snapshot per session for reproducibility.
    session.quiz_snapshot = select_quiz_snapshot(seed=session.id)
    session.save(update_fields=["quiz_snapshot"])
    LobbyParticipant.objects.get_or_create(session=session, user=host)
    _emit(session.id, "lobby.created", group_id=str(group.uuid))
    return session


def join_session(session: LobbySession, user) -> LobbyParticipant:
    """Add a group member to a waiting session (idempotent)."""
    if session.status != LobbySession.Status.WAITING:
        raise LobbyError("lobby roster is frozen; cannot join after start")
    _require_group_member(session.group, user)
    participant, _ = LobbyParticipant.objects.get_or_create(session=session, user=user)
    return participant


def submit_quiz_answers(session: LobbySession, user, answers: dict[str, str]) -> LobbyParticipant:
    """Validate and store this participant's answers against the snapshot."""
    participant = _get_participant(session, user)
    validated = validate_quiz_answers(session.quiz_snapshot, answers)
    participant.quiz_answers = validated
    participant.save(update_fields=["quiz_answers"])
    return participant


def _promote_next_queued(session: LobbySession) -> LobbyCard | None:
    """Make the lowest-position queued card current; None if queue empty."""
    nxt = LobbyCard.objects.filter(session=session, status=LobbyCard.Status.QUEUED).order_by("position", "id").first()
    if nxt is None:
        return None
    nxt.status = LobbyCard.Status.CURRENT
    nxt.save(update_fields=["status"])
    return nxt


def queue_movies(
    session: LobbySession,
    movies: list[Movie],
    *,
    source: str = LobbyCard.Source.SYSTEM,
    picked_by=None,
) -> list[LobbyCard]:
    """Queue movies as cards, skipping session dupes and group-listed titles.

    Respects `MAX_QUEUED_CARDS`. Pure DB write; no network calls.
    """
    existing_movie_ids = set(session.cards.values_list("movie_id", flat=True))
    group_movie_ids = set(GroupMovie.objects.filter(group=session.group).values_list("movie_id", flat=True))
    queued_count = session.cards.filter(status=LobbyCard.Status.QUEUED).count()
    top = session.cards.aggregate(m=Max("position"))["m"] or 0

    created: list[LobbyCard] = []
    for movie in movies:
        if movie.id in existing_movie_ids:
            continue
        if movie.id in group_movie_ids:
            continue
        if queued_count >= rules.MAX_QUEUED_CARDS:
            break
        top += 1
        card, was_created = LobbyCard.objects.get_or_create(
            session=session,
            movie=movie,
            defaults={"source": source, "picked_by": picked_by, "position": top},
        )
        if was_created:
            created.append(card)
            existing_movie_ids.add(movie.id)
            queued_count += 1
    return created


def nominate_manual_movie(session: LobbySession, user, movie: Movie) -> LobbyCard:
    """Queue a manual pick ahead of untouched system cards.

    Does not interrupt the current card. Duplicate nominations return the
    existing card; group-listed movies are rejected.
    """
    participant = _get_participant(session, user)
    if session.status not in (LobbySession.Status.WAITING, LobbySession.Status.ACTIVE):
        raise LobbyError("cannot nominate into a finished lobby")
    if GroupMovie.objects.filter(group=session.group, movie=movie).exists():
        raise LobbyError("movie is already in the group list")
    existing = LobbyCard.objects.filter(session=session, movie=movie).first()
    if existing is not None:
        return existing

    with transaction.atomic():
        locked = LobbySession.objects.select_for_update().get(pk=session.pk)
        current = locked.cards.filter(status=LobbyCard.Status.CURRENT).first()
        if current is None:
            position = (locked.cards.aggregate(m=Max("position"))["m"] or 0) + 1
        else:
            # Insert directly after current; shift later queued cards back.
            position = current.position + 1
            locked.cards.filter(status=LobbyCard.Status.QUEUED, position__gte=position).update(
                position=F("position") + 1
            )
        card = LobbyCard.objects.create(
            session=locked,
            movie=movie,
            source=LobbyCard.Source.MANUAL,
            picked_by=participant.user,
            position=position,
        )
        _emit(locked.id, "lobby.nominated", card_id=card.id, movie_id=movie.id)
        return card


def start_session(session: LobbySession, user) -> LobbySession:
    """Freeze the roster and activate the lobby; host only."""
    with transaction.atomic():
        locked = LobbySession.objects.select_for_update().get(pk=session.pk)
        if locked.host_id != user.pk:
            raise LobbyError("only the host may start the lobby")
        if locked.status != LobbySession.Status.WAITING:
            raise LobbyError("lobby has already started")
        count = locked.participants.count()
        if count < rules.MIN_PARTICIPANTS_TO_START:
            raise LobbyError(f"need at least {rules.MIN_PARTICIPANTS_TO_START} participants to start")
        locked.participants.update(state=LobbyParticipant.State.ACTIVE)
        locked.status = LobbySession.Status.ACTIVE
        locked.started_at = timezone.now()
        locked.save(update_fields=["status", "started_at"])
        current = locked.cards.filter(status=LobbyCard.Status.CURRENT).first()
        if current is None:
            current = _promote_next_queued(locked)
        _emit(locked.id, "lobby.started", current_card_id=getattr(current, "id", None))
        locked.refresh_from_db()
        return locked


def end_session(session: LobbySession, user) -> LobbySession:
    """Host ends a stuck session; keeps cards/history/offers for recovery."""
    with transaction.atomic():
        locked = LobbySession.objects.select_for_update().get(pk=session.pk)
        if locked.host_id != user.pk:
            raise LobbyError("only the host may end the lobby")
        if locked.status not in (LobbySession.Status.WAITING, LobbySession.Status.ACTIVE):
            return locked
        locked.status = LobbySession.Status.CANCELLED
        locked.finished_at = timezone.now()
        locked.save(update_fields=["status", "finished_at"])
        _emit(locked.id, "lobby.ended", status=locked.status)
        return locked


def _frozen_participants(session: LobbySession) -> list[LobbyParticipant]:
    return list(session.participants.filter(state=LobbyParticipant.State.ACTIVE))


def _resolve_completed_card(session: LobbySession, card: LobbyCard, ballots: list[LobbyBallot]) -> BallotResult:
    choices = [b.choice for b in ballots]
    participant_count = len(_frozen_participants(session))
    submitted_count = len(ballots)

    if all(c == LobbyBallot.Choice.WANT for c in choices):
        card.status = LobbyCard.Status.MATCHED
        card.save(update_fields=["status"])
        GroupMovie.objects.get_or_create(group=session.group, movie=card.movie, defaults={"suggested_by": session.host})
        session.status = LobbySession.Status.MATCHED
        session.finished_at = timezone.now()
        session.resolved_count += 1
        session.save(update_fields=["status", "finished_at", "resolved_count"])
        _emit(session.id, "lobby.matched", card_id=card.id, movie_id=card.movie_id)
        return BallotResult("matched", session, card, submitted_count, participant_count)

    if any(c == LobbyBallot.Choice.WATCHED for c in choices):
        # Watched-it takes precedence over veto so mixed ballots still offer.
        card.status = LobbyCard.Status.WATCHED
        card.save(update_fields=["status"])
        session.resolved_count += 1
        offer = WatchlistOffer.objects.create(card=card)
        watcher_ids = {b.participant_id for b in ballots if b.choice == LobbyBallot.Choice.WATCHED}
        for participant in _frozen_participants(session):
            if participant.id in watcher_ids:
                continue
            WatchlistOfferResponse.objects.get_or_create(offer=offer, participant=participant)
        session.save(update_fields=["resolved_count"])
        outcome: CardOutcome = "watched"
        offer_id: int | None = offer.id
    else:
        card.status = LobbyCard.Status.VETOED
        card.save(update_fields=["status"])
        session.resolved_count += 1
        session.save(update_fields=["resolved_count"])
        outcome = "vetoed"
        offer_id = None

    if session.resolved_count >= rules.MAX_RESOLVED_CARDS:
        session.status = LobbySession.Status.EXHAUSTED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        _emit(session.id, "lobby.exhausted", reason="cap", card_id=card.id)
        session.refresh_from_db()
        card.refresh_from_db()
        return BallotResult(
            "exhausted" if outcome == "vetoed" else outcome, session, card, submitted_count, participant_count, offer_id
        )

    nxt = _promote_next_queued(session)
    if nxt is None:
        session.status = LobbySession.Status.EXHAUSTED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        _emit(session.id, "lobby.exhausted", reason="empty", card_id=card.id)
    else:
        _emit(session.id, "lobby.advanced", card_id=card.id, next_card_id=nxt.id)
    session.refresh_from_db()
    card.refresh_from_db()
    return BallotResult(outcome, session, card, submitted_count, participant_count, offer_id)


def submit_ballot(
    session: LobbySession | UUID,
    user,
    choice: str,
    *,
    card_id: int | None = None,
) -> BallotResult:
    """Submit the caller's ballot for the current card (idempotent).

    Personal library writes happen in the same transaction as the ballot:
    Want adds to watchlist even if later vetoed; Watched records history
    immediately. A retried request returns current state without side effects.
    """
    if choice not in LobbyBallot.Choice.values:
        raise LobbyError(f"invalid ballot choice: {choice!r}")
    session_id = session.id if isinstance(session, LobbySession) else session

    with transaction.atomic():
        locked_session = LobbySession.objects.select_for_update().get(pk=session_id)
        if locked_session.status != LobbySession.Status.ACTIVE:
            raise LobbyError("lobby is not active")
        try:
            participant = LobbyParticipant.objects.get(session=locked_session, user=user)
        except LobbyParticipant.DoesNotExist:
            raise LobbyError("caller is not a participant in this session") from None
        if participant.state != LobbyParticipant.State.ACTIVE:
            raise LobbyError("roster is not frozen for this participant")

        current = (
            LobbyCard.objects.select_for_update()
            .filter(session=locked_session, status=LobbyCard.Status.CURRENT)
            .first()
        )
        if current is None:
            raise LobbyError("no current card to vote on")
        if card_id is not None and card_id != current.id:
            raise LobbyError("ballot is for a stale card")

        existing = LobbyBallot.objects.filter(card=current, participant=participant).first()
        if existing is not None:
            # Idempotent retry: no repeated side effects.
            ballots = list(current.ballots.select_related("participant"))
            frozen = _frozen_participants(locked_session)
            if len(ballots) >= len(frozen):
                # Already resolved path; report stored outcome.
                outcome: CardOutcome = (
                    "matched"
                    if current.status == LobbyCard.Status.MATCHED
                    else "watched"
                    if current.status == LobbyCard.Status.WATCHED
                    else "vetoed"
                    if current.status == LobbyCard.Status.VETOED
                    else "pending"
                )
                offer = getattr(current, "watch_offer", None)
                return BallotResult(
                    outcome, locked_session, current, len(ballots), len(frozen), getattr(offer, "id", None)
                )
            return BallotResult("pending", locked_session, current, len(ballots), len(frozen))

        ballot = LobbyBallot.objects.create(card=current, participant=participant, choice=choice)

        # Same-transaction personal side effects.
        if choice == LobbyBallot.Choice.WANT:
            add_to_personal_watchlist(user, current.movie)
        elif choice == LobbyBallot.Choice.WATCHED:
            mark_personally_watched(user, current.movie)
        # NOT_INTERESTED intentionally leaves the personal library untouched.

        ballots = list(current.ballots.select_related("participant"))
        frozen = _frozen_participants(locked_session)
        if len(ballots) < len(frozen):
            _emit(locked_session.id, "lobby.ballot", card_id=current.id, submitted=len(ballots), total=len(frozen))
            return BallotResult("pending", locked_session, current, len(ballots), len(frozen))

        result = _resolve_completed_card(locked_session, current, ballots)
        # Refresh ballot FKs for callers inspecting result.
        ballot.refresh_from_db()
        return result


def respond_to_offer(offer_id: int, user, action: Literal["add", "dismiss"]) -> WatchlistOfferResponse:
    """Add the offered movie to the group list or dismiss (idempotent)."""
    if action not in ("add", "dismiss"):
        raise LobbyError(f"invalid offer action: {action!r}")
    with transaction.atomic():
        try:
            response = WatchlistOfferResponse.objects.select_for_update().get(
                pk__in=WatchlistOfferResponse.objects.filter(participant__user=user, offer_id=offer_id).values("pk")
            )
        except WatchlistOfferResponse.DoesNotExist:
            raise LobbyError("no pending offer for this user") from None
        offer = WatchlistOffer.objects.select_for_update().get(pk=response.offer_id)
        if response.status != WatchlistOfferResponse.Status.PENDING and offer.status != WatchlistOffer.Status.OPEN:
            return response
        if response.status != WatchlistOfferResponse.Status.PENDING:
            return response  # idempotent replay
        if offer.status != WatchlistOffer.Status.OPEN:
            response.status = WatchlistOfferResponse.Status.CLOSED
            response.responded_at = timezone.now()
            response.save(update_fields=["status", "responded_at"])
            return response

        session = LobbySession.objects.get(pk=offer.card.session_id)
        if action == "dismiss":
            response.status = WatchlistOfferResponse.Status.DISMISSED
            response.responded_at = timezone.now()
            response.save(update_fields=["status", "responded_at"])
            _emit(session.id, "lobby.offer_dismissed", offer_id=offer.id)
            return response

        # add: exactly one GroupMovie; close the rest.
        GroupMovie.objects.get_or_create(group=session.group, movie=offer.card.movie, defaults={"suggested_by": user})
        response.status = WatchlistOfferResponse.Status.ADDED
        response.responded_at = timezone.now()
        response.save(update_fields=["status", "responded_at"])
        offer.status = WatchlistOffer.Status.CLOSED
        offer.save(update_fields=["status"])
        WatchlistOfferResponse.objects.filter(offer=offer, status=WatchlistOfferResponse.Status.PENDING).exclude(
            pk=response.pk
        ).update(status=WatchlistOfferResponse.Status.CLOSED, responded_at=timezone.now())
        _emit(session.id, "lobby.offer_added", offer_id=offer.id, movie_id=offer.card.movie_id)
        return response


def get_session_state(session: LobbySession, user) -> dict:
    """Reconnect payload: current card, own ballot, counts, pending offers.

    Never exposes other participants' choices while ballots are incomplete.
    """
    participant = _get_participant(session, user)
    current = session.cards.filter(status=LobbyCard.Status.CURRENT).first()
    frozen = session.participants.filter(state=LobbyParticipant.State.ACTIVE)
    pending_offers = list(
        WatchlistOfferResponse.objects.filter(
            participant__session=session,
            participant__user=user,
            status=WatchlistOfferResponse.Status.PENDING,
        ).select_related("offer__card__movie")
    )
    own_ballot_choice = None
    submitted = 0
    if current is not None:
        submitted = current.ballots.count()
        own = current.ballots.filter(participant=participant).first()
        own_ballot_choice = own.choice if own else None
    return {
        "session_id": str(session.id),
        "status": session.status,
        "participant_count": frozen.count() or session.participants.count(),
        "submitted_count": submitted,
        "current_card": (
            {
                "id": current.id,
                "movie_id": current.movie_id,
                "title": current.movie.title,
                "status": current.status,
                "pitch": current.pitch,
            }
            if current
            else None
        ),
        "own_choice": own_ballot_choice,
        "pending_offers": [
            {"offer_id": r.offer_id, "movie_id": r.offer.card.movie_id, "title": r.offer.card.movie.title}
            for r in pending_offers
        ],
    }
