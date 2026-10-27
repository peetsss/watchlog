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


@dataclass(frozen=True, slots=True)
class PlayerRef:
    user_id: int
    username: str
    is_host: bool
    is_ready: bool


@dataclass(frozen=True, slots=True)
class FinalistRef:
    movie: MovieRef
    pick_count: int
    viewer_picked: bool


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
    players: tuple[PlayerRef, ...]
    player_count: int
    pool_size: int
    pool_index: int
    current_movie: MovieRef | None
    submitted_count: int
    viewer_vote: str | None
    finalists: tuple[FinalistRef, ...]
    viewer_pick: int | None
    winner: MovieRef | None
