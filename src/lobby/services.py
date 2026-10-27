from collections.abc import Iterable
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from groups.models import Group, GroupMovie
from lobby import engine, rules
from lobby.exceptions import (
    AlreadyActiveLobbyError,
    InvalidChoiceError,
    InvalidStateError,
    LobbyError,  # noqa: F401  # part of the public error contract
    LobbyNotFoundError,
    NotAMemberError,
    NotHostError,
    NotJoinableError,
)
from lobby.models import Lobby, LobbyMembership
from lobby.pool import resolve_pool
from lobby.selectors import get_active_group_lobby, get_lobby_for_member, get_state
from user.models import User

__all__ = [
    "advance",
    "create_lobby",
    "end_lobby",
    "finalize_lobby",
    "get_active_group_lobby",
    "get_lobby_for_member",
    "get_state",
    "join_lobby",
    "leave_lobby",
    "mark_ready",
    "pick",
    "vote",
]


def _get_locked_lobby(lobby_uuid: str | UUID) -> Lobby:
    try:
        return Lobby.objects.select_for_update().get(uuid=lobby_uuid)
    except Lobby.DoesNotExist as exc:
        raise LobbyNotFoundError(f"Lobby {lobby_uuid} not found") from exc


def _user_id(user: User) -> str:
    return str(user.pk)


def _require_member(lobby: Lobby, user: User) -> None:
    if not lobby.memberships.filter(user_id=user.pk).exists():
        raise NotAMemberError(f"User {user.pk} is not a member of lobby {lobby.uuid}")


def _require_host(lobby: Lobby, user: User) -> None:
    if lobby.host_id != user.pk:
        raise NotHostError(f"User {user.pk} is not the host of lobby {lobby.uuid}")


def _require_status(lobby: Lobby, *statuses: str) -> None:
    if lobby.status not in statuses:
        expected = "/".join(statuses)
        raise InvalidStateError(f"Lobby {lobby.uuid} is {lobby.status}, expected {expected}")


def _game_from_lobby(lobby: Lobby) -> engine.Game:
    pool = tuple(int(movie_id) for movie_id in (lobby.pool or []))
    current: int | None = None
    if lobby.status == rules.PLAYING and 0 <= lobby.pool_index < len(pool):
        current = pool[lobby.pool_index]
    players = frozenset(str(membership.user_id) for membership in lobby.memberships.all())
    ready = frozenset(user_id for user_id in (str(value) for value in (lobby.ready or [])) if user_id in players)
    votes: dict[int, dict[str, str]] = {}
    for movie_id, user_votes in (lobby.votes or {}).items():
        pruned = {str(user_id): str(choice) for user_id, choice in user_votes.items() if str(user_id) in players}
        if pruned:
            votes[int(movie_id)] = pruned
    picks = {
        str(user_id): int(movie_id) for user_id, movie_id in (lobby.picks or {}).items() if str(user_id) in players
    }
    return engine.Game(
        status=lobby.status,
        players=players,
        ready=ready,
        pool=pool,
        pool_index=lobby.pool_index,
        current=current,
        votes=votes,
        picks=picks,
        candidates=tuple(int(movie_id) for movie_id in (lobby.finalists or [])),
        winner=lobby.winner_movie_id,
    )


def _record_group_winner(lobby: Lobby, game: engine.Game) -> None:
    if lobby.type != rules.GROUP_LOBBY or lobby.group_id is None:
        return
    if game.status != rules.FINISHED or game.winner is None:
        return
    GroupMovie.objects.get_or_create(
        group_id=lobby.group_id,
        movie_id=game.winner,
        defaults={"suggested_by_id": lobby.host_id},
    )


def _commit(lobby: Lobby, before: engine.Game, after: engine.Game) -> Lobby:
    _record_group_winner(lobby, after)
    if before == after:
        return lobby
    now = timezone.now()
    lobby.status = after.status
    lobby.pool = list(after.pool)
    lobby.pool_index = after.pool_index
    lobby.ready = sorted(after.ready, key=int)
    lobby.votes = {str(movie_id): dict(user_votes) for movie_id, user_votes in after.votes.items()}
    lobby.picks = dict(after.picks)
    lobby.finalists = list(after.candidates)
    lobby.winner_movie_id = after.winner
    lobby.version += 1
    if after.status == rules.PLAYING and lobby.started_at is None:
        lobby.started_at = now
    if after.status == rules.FINISHED and lobby.finished_at is None:
        lobby.finished_at = now
    lobby.save(
        update_fields=[
            "status",
            "pool",
            "pool_index",
            "ready",
            "votes",
            "picks",
            "finalists",
            "winner_movie",
            "version",
            "started_at",
            "finished_at",
        ]
    )
    return lobby


def _membership_users(host: User, members: Iterable[User], group: Group | None) -> list[User]:
    candidates = list(group.members.all()) if group is not None else [host, *members]
    ordered: dict[int, User] = {host.pk: host}
    for user in candidates:
        ordered.setdefault(user.pk, user)
    return list(ordered.values())


def _create_memberships(lobby: Lobby, host: User, users: Iterable[User]) -> None:
    LobbyMembership.objects.bulk_create(
        [
            LobbyMembership(
                lobby=lobby,
                user=user,
                role=LobbyMembership.Roles.HOST if user.pk == host.pk else LobbyMembership.Roles.MEMBER,
            )
            for user in users
        ]
    )


def create_lobby(
    host: User,
    members: Iterable[User] = (),
    group: Group | None = None,
    pool_size: int = rules.POOL_SIZE,
    pool: Iterable[int] | None = None,
) -> Lobby:
    lobby_type = Lobby.Type.GROUP if group is not None else Lobby.Type.OPEN
    with transaction.atomic():
        if group is not None:
            if not group.members.filter(pk=host.pk).exists():
                raise NotAMemberError(f"User {host.pk} is not a member of group {group.pk}")
            if Lobby.objects.filter(group=group, status__in=list(rules.ACTIVE_STATUSES)).exists():
                raise AlreadyActiveLobbyError(f"Group {group.pk} already has an active lobby")
        movie_ids = resolve_pool(pool, group=group, size=pool_size)
        try:
            with transaction.atomic():
                lobby = Lobby.objects.create(
                    type=lobby_type,
                    group=group,
                    host=host,
                    status=Lobby.Status.READY,
                    pool=movie_ids,
                    pool_index=0,
                    ready=[],
                    votes={},
                    picks={},
                    finalists=[],
                    version=0,
                )
        except IntegrityError as exc:
            if group is None:
                raise
            raise AlreadyActiveLobbyError(f"Group {group.pk} already has an active lobby") from exc
        _create_memberships(lobby, host, _membership_users(host, members, group))
        return lobby


def join_lobby(lobby_uuid: str | UUID, user: User) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        if lobby.type != Lobby.Type.OPEN:
            raise NotJoinableError("Only open lobbies can be joined")
        if lobby.memberships.filter(user_id=user.pk).exists():
            return lobby
        if lobby.status != Lobby.Status.READY:
            raise NotJoinableError("The lobby is not accepting new members")
        LobbyMembership.objects.create(lobby=lobby, user=user, role=LobbyMembership.Roles.MEMBER)
        lobby.version += 1
        lobby.save(update_fields=["version"])
        return lobby


def leave_lobby(lobby_uuid: str | UUID, user: User) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        if lobby.host_id == user.pk:
            raise NotAMemberError("The host cannot leave the lobby")
        _require_member(lobby, user)
        _require_status(lobby, rules.READY, rules.PLAYING, rules.FINAL_ROUND)
        before = _game_from_lobby(lobby)
        lobby.memberships.filter(user_id=user.pk).delete()
        after = engine.reconcile(_game_from_lobby(lobby))
        return _commit(lobby, before, after)


def mark_ready(lobby_uuid: str | UUID, user: User) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        _require_member(lobby, user)
        _require_status(lobby, rules.READY)
        before = _game_from_lobby(lobby)
        after = engine.mark_ready(before, _user_id(user))
        return _commit(lobby, before, after)


def vote(lobby_uuid: str | UUID, user: User, movie_id: int, choice: str) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        _require_member(lobby, user)
        if choice not in rules.VOTE_CHOICES:
            raise InvalidChoiceError(f"Unknown vote choice: {choice!r}")
        _require_status(lobby, rules.PLAYING)
        before = _game_from_lobby(lobby)
        if before.current is None:
            return _commit(lobby, before, engine.reconcile(before))
        if movie_id != before.current:
            return lobby
        after = engine.vote(before, _user_id(user), movie_id, choice)
        return _commit(lobby, before, after)


def pick(lobby_uuid: str | UUID, user: User, movie_id: int) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        _require_member(lobby, user)
        _require_status(lobby, rules.FINAL_ROUND)
        before = _game_from_lobby(lobby)
        if movie_id not in before.candidates:
            raise InvalidChoiceError(f"Movie {movie_id} is not a finalist in lobby {lobby.uuid}")
        after = engine.pick(before, _user_id(user), movie_id)
        return _commit(lobby, before, after)


def advance(lobby_uuid: str | UUID, user: User) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        _require_host(lobby, user)
        _require_status(lobby, rules.PLAYING)
        before = _game_from_lobby(lobby)
        after = engine.reconcile(before) if before.current is None else engine.advance(before)
        return _commit(lobby, before, after)


def finalize_lobby(lobby_uuid: str | UUID, user: User) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        _require_host(lobby, user)
        _require_status(lobby, rules.FINAL_ROUND)
        before = _game_from_lobby(lobby)
        after = engine.finalize(before)
        return _commit(lobby, before, after)


def end_lobby(lobby_uuid: str | UUID, user: User) -> Lobby:
    with transaction.atomic():
        lobby = _get_locked_lobby(lobby_uuid)
        _require_host(lobby, user)
        if lobby.status == Lobby.Status.FINISHED:
            return lobby
        _require_status(lobby, rules.READY, rules.PLAYING, rules.FINAL_ROUND)
        before = _game_from_lobby(lobby)
        after = engine.end(before)
        return _commit(lobby, before, after)
