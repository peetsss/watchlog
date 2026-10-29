from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MovieRef:
    id: int
    tmdb_id: int | None
    title: str
    release_date: date | None
    poster_path: str | None
    backdrop_path: str | None
    description: str | None
    runtime: int | None
    genres: str | None
    director: str | None


@dataclass(frozen=True, slots=True)
class PlayerRef:
    user_id: int
    username: str
    is_host: bool
    is_ready: bool


@dataclass(frozen=True, slots=True)
class BallotEntry:
    user_id: int
    username: str
    choice: str


@dataclass(frozen=True, slots=True)
class VoteTally:
    interested: int
    watched: int
    not_interested: int


@dataclass(frozen=True, slots=True)
class FinalistRef:
    movie: MovieRef
    pick_count: int | None
    viewer_picked: bool


@dataclass(frozen=True, slots=True)
class Capabilities:
    can_start: bool
    can_unready: bool
    can_advance: bool
    can_next_round: bool
    can_finalize: bool
    can_end: bool
    can_leave: bool
    can_restart: bool


@dataclass(frozen=True, slots=True)
class LobbyState:
    uuid: UUID
    type: str
    status: str
    version: int
    host_id: int | None
    group_uuid: UUID | None
    group_name: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    viewer_id: int
    viewer_is_host: bool
    viewer_ready: bool
    players: tuple[PlayerRef, ...]
    player_count: int
    ready_count: int
    pool_size: int
    pool_index: int
    round_number: int
    remaining_count: int
    current_movie: MovieRef | None
    submitted_count: int
    viewer_vote: str | None
    revealed: bool
    vote_tally: VoteTally | None
    ballot: tuple[BallotEntry, ...]
    finalists: tuple[FinalistRef, ...]
    picks_revealed: bool
    viewer_pick: int | None
    winner: MovieRef | None
    capabilities: Capabilities


@dataclass(frozen=True, slots=True)
class JoinPreview:
    uuid: UUID
    type: str
    status: str
    group_uuid: UUID | None
    group_name: str | None
    host_username: str | None
    player_count: int
    can_join: bool
    is_member: bool


@dataclass(frozen=True, slots=True)
class LobbySummary:
    uuid: UUID
    type: str
    status: str
    group_uuid: UUID | None
    group_name: str | None
    host_username: str | None
    player_count: int
    current_movie_title: str | None
    created_at: datetime
