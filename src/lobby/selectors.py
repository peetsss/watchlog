from uuid import UUID

from groups.models import Group
from lobby import rules
from lobby.dto import (
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
from lobby.exceptions import LobbyNotFoundError, NotAMemberError
from lobby.models import Lobby, LobbyMembership
from movies.models import Movie
from user.models import User


def _get_lobby(lobby_uuid: str | UUID) -> Lobby:
    try:
        return Lobby.objects.select_related("group", "winner_movie").get(uuid=lobby_uuid)
    except Lobby.DoesNotExist as exc:
        raise LobbyNotFoundError(f"Lobby {lobby_uuid} not found") from exc


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _movie_ref(movie: Movie | None) -> MovieRef | None:
    if movie is None:
        return None
    return MovieRef(
        id=movie.id,
        tmdb_id=movie.tmdb_id,
        title=movie.title,
        release_date=movie.release_date,
        poster_path=movie.poster_path,
        backdrop_path=movie.backdrop_path,
        description=movie.description,
        runtime=movie.runtime,
        genres=movie.genres,
        director=movie.director,
    )


def _current_movie_id(lobby: Lobby) -> int | None:
    if lobby.status != rules.PLAYING:
        return None
    pool = lobby.pool or []
    if 0 <= lobby.pool_index < len(pool):
        return int(pool[lobby.pool_index])
    return None


def _vote_map(lobby: Lobby, current_id: int | None) -> dict[str, str]:
    if current_id is None:
        return {}
    raw = (lobby.votes or {}).get(str(current_id), {})
    return {str(user_id): str(choice) for user_id, choice in raw.items()}


def _pick_counts(lobby: Lobby, players: set[str]) -> dict[int, int] | None:
    if not lobby.picks_revealed:
        return None
    counts: dict[int, int] = {}
    for user_id, raw_movie_id in (lobby.picks or {}).items():
        if str(user_id) not in players:
            continue
        movie_id = _as_int(str(raw_movie_id))
        if movie_id is not None:
            counts[movie_id] = counts.get(movie_id, 0) + 1
    return counts


def _submitted_count(lobby: Lobby, player_ids: set[int], current_id: int | None) -> int:
    if lobby.status == rules.PLAYING and current_id is not None:
        return sum(1 for user_id in _vote_map(lobby, current_id) if _as_int(user_id) in player_ids)
    if lobby.status == rules.FINAL_ROUND:
        return sum(1 for user_id in (lobby.picks or {}) if _as_int(user_id) in player_ids)
    return 0


def _vote_tally(lobby: Lobby, current_id: int | None, player_ids: set[int]) -> VoteTally | None:
    if not lobby.revealed or current_id is None:
        return None
    counts = {rules.INTERESTED: 0, rules.WATCHED: 0, rules.NOT_INTERESTED: 0}
    for user_id, choice in _vote_map(lobby, current_id).items():
        if _as_int(user_id) in player_ids and choice in counts:
            counts[choice] += 1
    return VoteTally(
        interested=counts[rules.INTERESTED],
        watched=counts[rules.WATCHED],
        not_interested=counts[rules.NOT_INTERESTED],
    )


def _ballot(
    lobby: Lobby,
    memberships: list[LobbyMembership],
    current_id: int | None,
    player_ids: set[int],
) -> tuple[BallotEntry, ...]:
    if not lobby.revealed or current_id is None:
        return ()
    vote_map = _vote_map(lobby, current_id)
    entries: list[BallotEntry] = []
    for membership in memberships:
        if membership.user_id not in player_ids:
            continue
        choice = vote_map.get(str(membership.user_id))
        if choice is None:
            continue
        entries.append(
            BallotEntry(
                user_id=membership.user_id,
                username=membership.user.username,
                choice=choice,
            )
        )
    return tuple(entries)


def _round_progress(lobby: Lobby) -> tuple[int, int]:
    pool_size = len(lobby.pool or [])
    if lobby.status == rules.PLAYING:
        return lobby.pool_index + 1, max(pool_size - lobby.pool_index, 0)
    if lobby.status == rules.FINAL_ROUND:
        return lobby.pool_index + 1, 0
    return 0, 0


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


def get_lobby_for_member(lobby_uuid: str | UUID, viewer: User) -> Lobby:
    lobby = _get_lobby(lobby_uuid)
    if not lobby.memberships.filter(user_id=viewer.pk).exists():
        raise NotAMemberError(f"User {viewer.pk} is not a member of lobby {lobby.uuid}")
    return lobby


def get_active_group_lobby(group: Group) -> Lobby | None:
    return (
        Lobby.objects.select_related("group", "winner_movie")
        .filter(group=group, status__in=list(rules.ACTIVE_STATUSES))
        .order_by("-created_at", "-id")
        .first()
    )


def get_state(lobby_uuid: str | UUID, viewer: User) -> LobbyState:
    lobby = _get_lobby(lobby_uuid)
    memberships = list(lobby.memberships.select_related("user").order_by("joined_at", "id"))
    if not any(membership.user_id == viewer.pk for membership in memberships):
        raise NotAMemberError(f"User {viewer.pk} is not a member of lobby {lobby.uuid}")

    ready_ids = {str(user_id) for user_id in (lobby.ready or [])}
    ordered = sorted(
        memberships, key=lambda membership: (membership.user_id != lobby.host_id, membership.joined_at, membership.id)
    )
    players = tuple(
        PlayerRef(
            user_id=membership.user_id,
            username=membership.user.username,
            is_host=membership.user_id == lobby.host_id,
            is_ready=str(membership.user_id) in ready_ids,
        )
        for membership in ordered
    )
    player_ids = {membership.user_id for membership in memberships}
    player_id_strings = {str(user_id) for user_id in player_ids}
    viewer_ready = str(viewer.pk) in ready_ids
    viewer_is_host = lobby.host_id == viewer.pk

    current_id = _current_movie_id(lobby)
    vote_map = _vote_map(lobby, current_id)
    finalist_ids = tuple(int(movie_id) for movie_id in (lobby.finalists or []))
    pick_counts = _pick_counts(lobby, player_id_strings)
    raw_pick = (lobby.picks or {}).get(str(viewer.pk))
    viewer_pick = _as_int(str(raw_pick)) if raw_pick is not None else None
    round_number, remaining_count = _round_progress(lobby)

    movie_ids = set(finalist_ids)
    if current_id is not None:
        movie_ids.add(current_id)
    if lobby.winner_movie_id is not None:
        movie_ids.add(lobby.winner_movie_id)
    movies = Movie.objects.in_bulk(movie_ids) if movie_ids else {}

    finalists: list[FinalistRef] = []
    for movie_id in finalist_ids:
        movie = _movie_ref(movies.get(movie_id))
        if movie is None:
            continue
        finalists.append(
            FinalistRef(
                movie=movie,
                pick_count=pick_counts.get(movie_id, 0) if pick_counts is not None else None,
                viewer_picked=viewer_pick == movie_id,
            )
        )

    return LobbyState(
        uuid=lobby.uuid,
        type=lobby.type,
        status=lobby.status,
        version=lobby.version,
        host_id=lobby.host_id,
        group_uuid=lobby.group.uuid if lobby.group_id is not None else None,
        group_name=lobby.group.name if lobby.group_id is not None else None,
        created_at=lobby.created_at,
        started_at=lobby.started_at,
        finished_at=lobby.finished_at,
        viewer_id=viewer.pk,
        viewer_is_host=viewer_is_host,
        viewer_ready=viewer_ready,
        players=players,
        player_count=len(players),
        ready_count=sum(1 for player in players if player.is_ready),
        pool_size=len(lobby.pool or []),
        pool_index=lobby.pool_index,
        round_number=round_number,
        remaining_count=remaining_count,
        current_movie=_movie_ref(movies.get(current_id)) if current_id is not None else None,
        submitted_count=_submitted_count(lobby, player_ids, current_id),
        viewer_vote=vote_map.get(str(viewer.pk)),
        revealed=lobby.revealed,
        vote_tally=_vote_tally(lobby, current_id, player_ids),
        ballot=_ballot(lobby, ordered, current_id, player_ids),
        finalists=tuple(finalists),
        picks_revealed=lobby.picks_revealed,
        viewer_pick=viewer_pick,
        winner=_movie_ref(movies.get(lobby.winner_movie_id)) if lobby.winner_movie_id is not None else None,
        capabilities=_capabilities(lobby, viewer_is_host, viewer_ready),
    )


def get_join_preview(lobby_uuid: str | UUID, viewer: User) -> JoinPreview:
    lobby = _get_lobby(lobby_uuid)
    is_member = lobby.memberships.filter(user_id=viewer.pk).exists()
    player_count = lobby.memberships.count()
    return JoinPreview(
        uuid=lobby.uuid,
        type=lobby.type,
        status=lobby.status,
        group_uuid=lobby.group.uuid if lobby.group_id is not None else None,
        group_name=lobby.group.name if lobby.group_id is not None else None,
        host_username=lobby.host.username if lobby.host_id is not None else None,
        player_count=player_count,
        can_join=lobby.type == rules.OPEN_LOBBY and lobby.status == rules.READY and not is_member,
        is_member=is_member,
    )


def get_active_lobby_for_user(viewer: User) -> LobbySummary | None:
    lobby = (
        Lobby.objects.select_related("group", "host", "winner_movie")
        .filter(memberships__user=viewer, status__in=list(rules.ACTIVE_STATUSES))
        .order_by("-created_at", "-id")
        .first()
    )
    if lobby is None:
        return None
    player_count = lobby.memberships.count()
    current_movie_title: str | None = None
    if lobby.status == rules.PLAYING:
        pool = lobby.pool or []
        if 0 <= lobby.pool_index < len(pool):
            current_movie_title = (
                Movie.objects.filter(pk=int(pool[lobby.pool_index])).values_list("title", flat=True).first()
            )
    return LobbySummary(
        uuid=lobby.uuid,
        type=lobby.type,
        status=lobby.status,
        group_uuid=lobby.group.uuid if lobby.group_id is not None else None,
        group_name=lobby.group.name if lobby.group_id is not None else None,
        host_username=lobby.host.username if lobby.host_id is not None else None,
        player_count=player_count,
        current_movie_title=current_movie_title,
        created_at=lobby.created_at,
    )
