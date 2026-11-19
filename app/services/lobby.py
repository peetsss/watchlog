import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.lobby import engine, rules
from app.domain.lobby.exceptions import (
    AlreadyActiveLobbyError,
    InvalidChoiceError,
    InvalidStateError,
    LobbyNotFoundError,
    NotAMemberError,
    NotHostError,
    NotJoinableError,
)
from app.models.group import Group, GroupMembership, GroupMovie
from app.models.guest import Guest
from app.models.lobby import Lobby, LobbyParticipant, LobbyPick, LobbyVote
from app.models.movie import Movie
from app.models.user import User
from app.realtime.events import LobbyChanged, LobbyRestarted
from app.schemas.lobby import (
    BallotEntry,
    Capabilities,
    FinalistRef,
    JoinPreview,
    LobbyState,
    LobbySummary,
    MovieRef,
    PlayerRef,
    VoteTally,
)
from app.services.identity import Viewer
from app.services.lobby_pool import resolve_pool
from app.services.viewer import color_for, initials_for
from app.services.watch_providers import load_cached_availability

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


async def _get_lobby(db: AsyncSession, lobby_id: UUID, *, lock: bool = False) -> Lobby:
    statement = select(Lobby).where(Lobby.id == lobby_id)
    if lock:
        statement = statement.with_for_update()
    lobby = await db.scalar(statement)
    if lobby is None:
        raise LobbyNotFoundError("This room is no longer available.")
    return lobby


async def _participants(db: AsyncSession, lobby_id: UUID) -> list[LobbyParticipant]:
    return list(
        await db.scalars(
            select(LobbyParticipant)
            .where(LobbyParticipant.lobby_id == lobby_id)
            .order_by(LobbyParticipant.joined_at, LobbyParticipant.id)
        )
    )


def _find_participant(participants: list[LobbyParticipant], viewer: Viewer) -> LobbyParticipant | None:
    for participant in participants:
        if viewer.user_id is not None and participant.user_id == viewer.user_id:
            return participant
        if viewer.guest_id is not None and participant.guest_id == viewer.guest_id:
            return participant
    return None


def _participant_for_viewer(participants: list[LobbyParticipant], viewer: Viewer) -> LobbyParticipant:
    participant = _find_participant(participants, viewer)
    if participant is None:
        raise NotAMemberError("You are not a participant in this room.")
    return participant


def _host_participant(participants: list[LobbyParticipant], lobby: Lobby) -> LobbyParticipant | None:
    for participant in participants:
        if participant.id == lobby.host_participant_id:
            return participant
    return None


def _require_host(participants: list[LobbyParticipant], lobby: Lobby, viewer: Viewer) -> LobbyParticipant:
    host = _host_participant(participants, lobby)
    participant = _participant_for_viewer(participants, viewer)
    if host is None or host.id != participant.id:
        raise NotHostError("Only the host can do that.")
    return host


def _require_status(lobby: Lobby, *statuses: str) -> None:
    if lobby.status not in statuses:
        raise InvalidStateError("That action is not available right now.")


def _current_movie_id(lobby: Lobby) -> int | None:
    if lobby.status != rules.PLAYING:
        return None
    pool = lobby.pool or []
    if 0 <= lobby.pool_index < len(pool):
        return int(pool[lobby.pool_index])
    return None


async def _game_from_lobby(
    db: AsyncSession,
    lobby: Lobby,
    participants: list[LobbyParticipant],
) -> engine.Game:
    player_ids = {str(participant.id) for participant in participants}
    ready = frozenset(str(participant.id) for participant in participants if participant.is_ready)

    votes: dict[int, dict[str, str]] = {}
    for vote in await db.scalars(select(LobbyVote).where(LobbyVote.lobby_id == lobby.id)):
        participant_id = str(vote.participant_id)
        if participant_id in player_ids:
            votes.setdefault(vote.movie_id, {})[participant_id] = vote.choice

    picks: dict[str, int] = {}
    for pick in await db.scalars(select(LobbyPick).where(LobbyPick.lobby_id == lobby.id)):
        participant_id = str(pick.participant_id)
        if participant_id in player_ids:
            picks[participant_id] = pick.movie_id

    return engine.Game(
        status=lobby.status,
        players=frozenset(player_ids),
        ready=ready,
        pool=tuple(int(movie_id) for movie_id in (lobby.pool or [])),
        pool_index=lobby.pool_index,
        current=_current_movie_id(lobby),
        votes=votes,
        picks=picks,
        candidates=tuple(int(movie_id) for movie_id in (lobby.finalists or [])),
        winner=lobby.winner_movie_id,
        revealed=lobby.revealed,
        picks_revealed=lobby.picks_revealed,
    )


async def _record_group_winner(db: AsyncSession, lobby: Lobby, game: engine.Game) -> None:
    if lobby.type != rules.GROUP_LOBBY or lobby.group_id is None:
        return
    if game.status != rules.FINISHED or game.winner is None:
        return
    existing = await db.scalar(
        select(GroupMovie).where(
            GroupMovie.group_id == lobby.group_id,
            GroupMovie.movie_id == game.winner,
        )
    )
    if existing is not None:
        return
    host = await db.scalar(select(LobbyParticipant).where(LobbyParticipant.id == lobby.host_participant_id))
    db.add(
        GroupMovie(
            group_id=lobby.group_id,
            movie_id=game.winner,
            suggested_by_id=host.user_id if host is not None else None,
        )
    )


async def _commit(
    db: AsyncSession,
    lobby: Lobby,
    participants: list[LobbyParticipant],
    before: engine.Game,
    after: engine.Game,
    reason: str = "change",
) -> Lobby:
    await _record_group_winner(db, lobby, after)
    if before == after:
        return lobby

    lobby.status = after.status
    lobby.pool = list(after.pool)
    lobby.pool_index = after.pool_index
    lobby.finalists = list(after.candidates)
    lobby.winner_movie_id = after.winner
    lobby.revealed = after.revealed
    lobby.picks_revealed = after.picks_revealed
    lobby.version += 1
    now = _now()
    if after.status == rules.PLAYING and lobby.started_at is None:
        lobby.started_at = now
    if after.status == rules.FINISHED and lobby.finished_at is None:
        lobby.finished_at = now

    ready_ids = {str(participant_id) for participant_id in after.ready}
    for participant in participants:
        participant.is_ready = str(participant.id) in ready_ids

    await db.execute(delete(LobbyVote).where(LobbyVote.lobby_id == lobby.id))
    await db.execute(delete(LobbyPick).where(LobbyPick.lobby_id == lobby.id))
    for movie_id, user_votes in after.votes.items():
        for participant_id, choice in user_votes.items():
            db.add(
                LobbyVote(
                    lobby_id=lobby.id,
                    movie_id=movie_id,
                    participant_id=UUID(participant_id),
                    choice=choice,
                )
            )
    for participant_id, movie_id in after.picks.items():
        db.add(
            LobbyPick(
                lobby_id=lobby.id,
                participant_id=UUID(participant_id),
                movie_id=movie_id,
            )
        )

    await db.commit()
    await _publish(db, LobbyChanged(lobby.id, lobby.version, reason))
    return lobby


async def _publish(db: AsyncSession, event: LobbyChanged | LobbyRestarted) -> None:
    publisher = db.info.get("lobby_publisher")
    if publisher is None:
        return
    try:
        await publisher(event)
    except Exception:
        logger.exception("Failed to publish a lobby event")


async def create_lobby(
    db: AsyncSession,
    host: Viewer,
    group: Group | None = None,
    members: tuple[User, ...] = (),
    extra_viewers: tuple[Viewer, ...] = (),
    participants_override: tuple[Viewer, ...] | None = None,
    pool_size: int = rules.POOL_SIZE,
    pool: list[int] | None = None,
) -> Lobby:
    host_user = host.user
    if group is not None:
        if host_user is None:
            raise NotAMemberError("Guests cannot create group rooms.")
        membership = await db.scalar(
            select(GroupMembership).where(
                GroupMembership.group_id == group.id,
                GroupMembership.user_id == host_user.id,
            )
        )
        if membership is None:
            raise NotAMemberError("You are not a member of this group.")
        active = await db.scalar(
            select(Lobby.id).where(
                Lobby.group_id == group.id,
                Lobby.status.in_(list(rules.ACTIVE_STATUSES)),
            )
        )
        if active is not None:
            raise AlreadyActiveLobbyError("This group already has an active room.")

    lobby_type = rules.GROUP_LOBBY if group is not None else rules.OPEN_LOBBY
    movie_ids = await resolve_pool(db, pool, group=group, size=pool_size)
    lobby = Lobby(
        type=lobby_type,
        group_id=group.id if group is not None else None,
        status=rules.READY,
        pool=movie_ids,
        pool_index=0,
        finalists=[],
        revealed=False,
        picks_revealed=False,
        version=0,
    )
    db.add(lobby)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if group is not None:
            raise AlreadyActiveLobbyError("This group already has an active room.") from exc
        raise

    if participants_override is not None:
        candidate_viewers = list(participants_override)
    elif group is not None:
        users = list(
            await db.scalars(
                select(User)
                .join(GroupMembership, GroupMembership.user_id == User.id)
                .where(GroupMembership.group_id == group.id)
                .order_by(User.username)
            )
        )
        candidate_viewers = [Viewer.for_user(user) for user in users]
    else:
        candidate_viewers = [
            host,
            *(Viewer.for_user(member) for member in members),
            *extra_viewers,
        ]

    users: list[Viewer] = []
    seen: set[str] = set()
    for viewer in candidate_viewers:
        if viewer.identity_key in seen:
            continue
        users.append(viewer)
        seen.add(viewer.identity_key)

    participants: list[LobbyParticipant] = []
    for viewer in users:
        participant = LobbyParticipant(
            lobby_id=lobby.id,
            user_id=viewer.user_id,
            guest_id=viewer.guest_id,
            display_name=viewer.display_name,
        )
        db.add(participant)
        participants.append(participant)
    await db.flush()

    host_participant = next(
        (
            participant
            for participant in participants
            if (host.user_id is not None and participant.user_id == host.user_id)
            or (host.guest_id is not None and participant.guest_id == host.guest_id)
        ),
        None,
    )
    if host_participant is None:
        raise NotAMemberError("You are not a participant in this room.")
    lobby.host_participant_id = host_participant.id
    await db.commit()
    await db.refresh(lobby)
    return lobby


async def join_lobby(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    if _find_participant(participants, viewer) is not None:
        return lobby
    if lobby.type != rules.OPEN_LOBBY:
        raise NotJoinableError("Only open lobbies can be joined")
    if lobby.status != rules.READY:
        raise NotJoinableError("The lobby is not accepting new members")
    if any(participant.display_name.casefold() == viewer.display_name.casefold() for participant in participants):
        raise NotJoinableError("That display name is taken in this room")

    db.add(
        LobbyParticipant(
            lobby_id=lobby.id,
            user_id=viewer.user_id,
            guest_id=viewer.guest_id,
            display_name=viewer.display_name,
        )
    )
    lobby.version += 1
    await db.commit()
    await db.refresh(lobby)
    await _publish(db, LobbyChanged(lobby.id, lobby.version, "join"))
    return lobby


async def leave_lobby(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    participant = _participant_for_viewer(participants, viewer)
    if participant.id == lobby.host_participant_id:
        raise NotAMemberError("The host cannot leave the room.")
    _require_status(lobby, rules.READY, rules.PLAYING, rules.FINAL_ROUND)

    before = await _game_from_lobby(db, lobby, participants)
    await db.delete(participant)
    await db.flush()
    participants = await _participants(db, lobby.id)
    after = engine.reconcile(await _game_from_lobby(db, lobby, participants))
    return await _commit(db, lobby, participants, before, after, reason="leave")


async def mark_ready(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    participant = _participant_for_viewer(participants, viewer)
    _require_status(lobby, rules.READY)
    before = await _game_from_lobby(db, lobby, participants)
    after = engine.mark_ready(before, str(participant.id))
    return await _commit(db, lobby, participants, before, after, reason="ready")


async def unready(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    participant = _participant_for_viewer(participants, viewer)
    _require_status(lobby, rules.READY)
    before = await _game_from_lobby(db, lobby, participants)
    after = engine.unready(before, str(participant.id))
    return await _commit(db, lobby, participants, before, after, reason="unready")


async def start_lobby(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    host = _require_host(participants, lobby, viewer)
    _require_status(lobby, rules.READY)
    before = await _game_from_lobby(db, lobby, participants)
    participating = before.ready | {str(host.id)}
    participating_ids = {UUID(participant_id) for participant_id in participating}
    for participant in participants:
        if participant.id not in participating_ids:
            await db.delete(participant)
    await db.flush()
    participants = await _participants(db, lobby.id)
    after = engine.start(await _game_from_lobby(db, lobby, participants), participating)
    return await _commit(db, lobby, participants, before, after, reason="start")


async def vote(db: AsyncSession, lobby_id: UUID, viewer: Viewer, movie_id: int, choice: str) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    participant = _participant_for_viewer(participants, viewer)
    if choice not in rules.VOTE_CHOICES:
        raise InvalidChoiceError("That vote is not valid.")
    _require_status(lobby, rules.PLAYING)
    if lobby.revealed:
        raise InvalidStateError("This film has already been revealed.")

    before = await _game_from_lobby(db, lobby, participants)
    if before.current is None:
        after = engine.reconcile(before)
        return await _commit(db, lobby, participants, before, after, reason="vote")
    if movie_id != before.current:
        return lobby
    after = engine.vote(before, str(participant.id), movie_id, choice)
    return await _commit(db, lobby, participants, before, after, reason="vote")


async def next_round(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    _participant_for_viewer(participants, viewer)
    _require_status(lobby, rules.PLAYING)
    if not lobby.revealed:
        raise InvalidStateError("This film has not been revealed yet.")
    before = await _game_from_lobby(db, lobby, participants)
    after = engine.next_round(before)
    return await _commit(db, lobby, participants, before, after, reason="next_round")


async def pick(db: AsyncSession, lobby_id: UUID, viewer: Viewer, movie_id: int) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    participant = _participant_for_viewer(participants, viewer)
    _require_status(lobby, rules.FINAL_ROUND)
    if lobby.picks_revealed:
        raise InvalidStateError("The final picks have already been revealed.")
    before = await _game_from_lobby(db, lobby, participants)
    if movie_id not in before.candidates:
        raise InvalidChoiceError("That film is not a finalist.")
    after = engine.pick(before, str(participant.id), movie_id)
    return await _commit(db, lobby, participants, before, after, reason="pick")


async def advance(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    _require_host(participants, lobby, viewer)
    _require_status(lobby, rules.PLAYING)
    if lobby.revealed:
        raise InvalidStateError("This film has already been revealed.")
    before = await _game_from_lobby(db, lobby, participants)
    after = engine.reconcile(before) if before.current is None else engine.advance(before)
    return await _commit(db, lobby, participants, before, after, reason="advance")


async def finalize_lobby(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    participant = _participant_for_viewer(participants, viewer)
    _require_status(lobby, rules.FINAL_ROUND)
    if not lobby.picks_revealed and participant.id != lobby.host_participant_id:
        raise NotHostError("Only the host can finalize before every pick is in.")
    before = await _game_from_lobby(db, lobby, participants)
    after = engine.finalize(before)
    return await _commit(db, lobby, participants, before, after, reason="finalize")


async def end_lobby(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    _require_host(participants, lobby, viewer)
    if lobby.status == rules.FINISHED:
        return lobby
    _require_status(lobby, rules.READY, rules.PLAYING, rules.FINAL_ROUND)
    before = await _game_from_lobby(db, lobby, participants)
    after = engine.end(before)
    return await _commit(db, lobby, participants, before, after, reason="end")


async def restart_lobby(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> Lobby:
    lobby = await _get_lobby(db, lobby_id, lock=True)
    participants = await _participants(db, lobby.id)
    _require_host(participants, lobby, viewer)
    _require_status(lobby, rules.FINISHED)
    if lobby.group_id is not None:
        group = await db.get(Group, lobby.group_id)
        if group is None:
            raise LobbyNotFoundError("This room is no longer available.")
        new_lobby = await create_lobby(db, viewer, group=group)
    else:
        viewers: list[Viewer] = []
        for participant in participants:
            if participant.user_id is not None:
                user_model = await db.get(User, participant.user_id)
                if user_model is not None:
                    viewers.append(Viewer.for_user(user_model))
            elif participant.guest_id is not None:
                guest = await db.get(Guest, participant.guest_id)
                if guest is not None:
                    viewers.append(Viewer.for_guest(guest))
        new_lobby = await create_lobby(db, viewer, participants_override=tuple(viewers))
    await _publish(db, LobbyRestarted(lobby.id, new_lobby.id))
    return new_lobby


async def get_active_lobby_for_viewer(db: AsyncSession, viewer: Viewer) -> LobbySummary | None:
    participant_identity = (
        LobbyParticipant.user_id == viewer.user_id
        if viewer.user_id is not None
        else LobbyParticipant.guest_id == viewer.guest_id
    )
    lobby = await db.scalar(
        select(Lobby)
        .join(LobbyParticipant, LobbyParticipant.lobby_id == Lobby.id)
        .where(
            participant_identity,
            Lobby.status.in_(list(rules.ACTIVE_STATUSES)),
        )
        .order_by(Lobby.created_at.desc(), Lobby.id.desc())
        .limit(1)
    )
    if lobby is None:
        return None
    return await _summary(db, lobby)


async def _summary(db: AsyncSession, lobby: Lobby) -> LobbySummary:
    participants = await _participants(db, lobby.id)
    host = _host_participant(participants, lobby)
    group = await db.get(Group, lobby.group_id) if lobby.group_id is not None else None
    current_title = None
    current_id = _current_movie_id(lobby)
    if current_id is not None:
        current_title = await db.scalar(select(Movie.title).where(Movie.id == current_id))
    return LobbySummary(
        uuid=lobby.id,
        type=lobby.type,
        status=lobby.status,
        group_uuid=group.id if group is not None else None,
        group_name=group.name if group is not None else None,
        host_username=host.display_name if host is not None else None,
        player_count=len(participants),
        current_movie_title=current_title,
        created_at=lobby.created_at,
    )


async def get_join_preview(db: AsyncSession, lobby_id: UUID, viewer: Viewer | None) -> JoinPreview:
    lobby = await _get_lobby(db, lobby_id)
    participants = await _participants(db, lobby.id)
    is_participant = viewer is not None and _find_participant(participants, viewer) is not None
    host = _host_participant(participants, lobby)
    group = await db.get(Group, lobby.group_id) if lobby.group_id is not None else None
    return JoinPreview(
        uuid=lobby.id,
        type=lobby.type,
        status=lobby.status,
        group_uuid=group.id if group is not None else None,
        group_name=group.name if group is not None else None,
        host_username=host.display_name if host is not None else None,
        player_count=len(participants),
        can_join=lobby.type == rules.OPEN_LOBBY and lobby.status == rules.READY and not is_participant,
        is_participant=is_participant,
    )


def _movie_ref(movie: Movie | None) -> MovieRef | None:
    return MovieRef.model_validate(movie) if movie is not None else None


async def _movie_map(db: AsyncSession, movie_ids: set[int]) -> dict[int, Movie]:
    if not movie_ids:
        return {}
    movies = list(await db.scalars(select(Movie).where(Movie.id.in_(movie_ids))))
    return {movie.id: movie for movie in movies}


def _capabilities(lobby: Lobby, viewer_is_host: bool, viewer_ready: bool) -> Capabilities:
    active = lobby.status in rules.ACTIVE_STATUSES
    return Capabilities(
        can_start=viewer_is_host and lobby.status == rules.READY,
        can_unready=viewer_ready and lobby.status == rules.READY,
        can_advance=viewer_is_host and lobby.status == rules.PLAYING and not lobby.revealed,
        can_next_round=lobby.status == rules.PLAYING and lobby.revealed,
        can_finalize=lobby.status == rules.FINAL_ROUND and (viewer_is_host or lobby.picks_revealed),
        can_end=viewer_is_host and active,
        can_leave=not viewer_is_host and active,
        can_restart=viewer_is_host and lobby.status == rules.FINISHED,
    )


def _round_progress(lobby: Lobby) -> tuple[int, int]:
    pool_size = len(lobby.pool or [])
    if lobby.status == rules.PLAYING:
        return lobby.pool_index + 1, max(pool_size - lobby.pool_index, 0)
    if lobby.status == rules.FINAL_ROUND:
        return lobby.pool_index + 1, 0
    return 0, 0


async def get_state(db: AsyncSession, lobby_id: UUID, viewer: Viewer) -> LobbyState:
    lobby = await _get_lobby(db, lobby_id)
    participants = await _participants(db, lobby.id)
    viewer_participant = _participant_for_viewer(participants, viewer)
    group = await db.get(Group, lobby.group_id) if lobby.group_id is not None else None
    participant_ids = {participant.id for participant in participants}

    picks: dict[str, int] = {}
    for pick_row in await db.scalars(select(LobbyPick).where(LobbyPick.lobby_id == lobby.id)):
        participant_id = str(pick_row.participant_id)
        if pick_row.participant_id in participant_ids:
            picks[participant_id] = pick_row.movie_id

    vote_map: dict[int, dict[str, str]] = {}
    for vote_row in await db.scalars(select(LobbyVote).where(LobbyVote.lobby_id == lobby.id)):
        if vote_row.participant_id not in participant_ids:
            continue
        vote_map.setdefault(vote_row.movie_id, {})[str(vote_row.participant_id)] = vote_row.choice

    current_id = _current_movie_id(lobby)
    current_votes = vote_map.get(current_id, {}) if current_id is not None else {}
    finalist_ids = tuple(int(movie_id) for movie_id in (lobby.finalists or []))
    movie_ids = set(finalist_ids)
    if current_id is not None:
        movie_ids.add(current_id)
    if lobby.winner_movie_id is not None:
        movie_ids.add(lobby.winner_movie_id)
    movies = await _movie_map(db, movie_ids)

    settings = get_settings()
    watch_region = viewer.user.region if viewer.user is not None else settings.default_region
    watch_movie_ids = set(finalist_ids)
    if lobby.winner_movie_id is not None:
        watch_movie_ids.add(lobby.winner_movie_id)
    watch_by_movie = await load_cached_availability(
        db,
        watch_movie_ids,
        watch_region,
        settings.watch_provider_ttl_seconds,
    )

    ordered = sorted(
        participants,
        key=lambda participant: (
            participant.id != lobby.host_participant_id,
            participant.joined_at,
            str(participant.id),
        ),
    )
    players = [
        PlayerRef(
            id=str(participant.id),
            name=participant.display_name,
            initials=initials_for(participant.display_name),
            color=color_for(participant.user_id if participant.user_id is not None else str(participant.guest_id)),
            is_host=participant.id == lobby.host_participant_id,
            is_guest=participant.guest_id is not None,
            is_ready=participant.is_ready,
        )
        for participant in ordered
    ]

    pick_counts: dict[int, int] | None = None
    if lobby.picks_revealed:
        pick_counts = {}
        for movie_id in picks.values():
            pick_counts[movie_id] = pick_counts.get(movie_id, 0) + 1

    finalists: list[FinalistRef] = []
    for movie_id in finalist_ids:
        movie = movies.get(movie_id)
        if movie is None:
            continue
        finalists.append(
            FinalistRef(
                movie=MovieRef.model_validate(movie),
                pick_count=pick_counts.get(movie_id, 0) if pick_counts is not None else None,
                viewer_picked=picks.get(str(viewer_participant.id)) == movie_id,
                watch=watch_by_movie.get(movie_id),
            )
        )

    total_votes = len(current_votes)
    vote_tally = None
    ballot: list[BallotEntry] = []
    if lobby.revealed and current_id is not None:
        counts = {rules.INTERESTED: 0, rules.WATCHED: 0, rules.NOT_INTERESTED: 0}
        for choice in current_votes.values():
            if choice in counts:
                counts[choice] += 1
        vote_tally = VoteTally(
            interested=counts[rules.INTERESTED],
            watched=counts[rules.WATCHED],
            not_interested=counts[rules.NOT_INTERESTED],
            total=sum(counts.values()),
        )
        for participant in ordered:
            choice = current_votes.get(str(participant.id))
            if choice is not None:
                ballot.append(
                    BallotEntry(
                        participant_id=str(participant.id),
                        name=participant.display_name,
                        choice=choice,
                    )
                )

    if lobby.status == rules.PLAYING and current_id is not None:
        submitted_count = total_votes
    elif lobby.status == rules.FINAL_ROUND:
        submitted_count = len(picks)
    else:
        submitted_count = 0

    round_number, remaining_count = _round_progress(lobby)
    viewer_is_host = viewer_participant.id == lobby.host_participant_id
    return LobbyState(
        uuid=lobby.id,
        type=lobby.type,
        status=lobby.status,
        version=lobby.version,
        host_id=str(lobby.host_participant_id) if lobby.host_participant_id is not None else None,
        group_uuid=group.id if group is not None else None,
        group_name=group.name if group is not None else None,
        created_at=lobby.created_at,
        started_at=lobby.started_at,
        finished_at=lobby.finished_at,
        viewer_id=str(viewer_participant.id),
        viewer_is_host=viewer_is_host,
        viewer_ready=viewer_participant.is_ready,
        players=players,
        player_count=len(players),
        ready_count=sum(1 for player in players if player.is_ready),
        pool_size=len(lobby.pool or []),
        pool_index=lobby.pool_index,
        round_number=round_number,
        remaining_count=remaining_count,
        current_movie=_movie_ref(movies.get(current_id)) if current_id is not None else None,
        submitted_count=submitted_count,
        viewer_vote=current_votes.get(str(viewer_participant.id)),
        revealed=lobby.revealed,
        vote_tally=vote_tally,
        ballot=ballot,
        finalists=finalists,
        picks_revealed=lobby.picks_revealed,
        viewer_pick=picks.get(str(viewer_participant.id)),
        winner=_movie_ref(movies.get(lobby.winner_movie_id)) if lobby.winner_movie_id is not None else None,
        winner_watch=watch_by_movie.get(lobby.winner_movie_id) if lobby.winner_movie_id is not None else None,
        capabilities=_capabilities(lobby, viewer_is_host, viewer_participant.is_ready),
    )
