from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.watch import WatchAvailability


class MovieRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class PlayerRef(BaseModel):
    id: str
    name: str
    initials: str
    color: str
    is_host: bool
    is_guest: bool
    is_ready: bool


class BallotEntry(BaseModel):
    participant_id: str
    name: str
    choice: str


class VoteTally(BaseModel):
    interested: int
    watched: int
    not_interested: int
    total: int


class FinalistRef(BaseModel):
    movie: MovieRef
    pick_count: int | None
    viewer_picked: bool
    watch: WatchAvailability | None = None


class Capabilities(BaseModel):
    can_start: bool
    can_unready: bool
    can_advance: bool
    can_next_round: bool
    can_finalize: bool
    can_end: bool
    can_leave: bool
    can_restart: bool


class LobbyState(BaseModel):
    uuid: UUID
    type: str
    status: str
    version: int
    host_id: str | None
    group_uuid: UUID | None
    group_name: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    viewer_id: str
    viewer_is_host: bool
    viewer_ready: bool
    players: list[PlayerRef]
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
    ballot: list[BallotEntry]
    finalists: list[FinalistRef]
    picks_revealed: bool
    viewer_pick: int | None
    winner: MovieRef | None
    winner_watch: WatchAvailability | None = None
    capabilities: Capabilities


class LobbyStateEnvelope(BaseModel):
    lobby: LobbyState


class JoinPreview(BaseModel):
    uuid: UUID
    type: Literal["group", "open"]
    status: str
    group_uuid: UUID | None
    group_name: str | None
    host_username: str | None
    player_count: int
    can_join: bool
    is_participant: bool
    is_group_member: bool = False


class JoinPreviewEnvelope(BaseModel):
    preview: JoinPreview


class LobbySummary(BaseModel):
    uuid: UUID
    type: Literal["group", "open"]
    status: str
    group_uuid: UUID | None
    group_name: str | None
    host_username: str | None
    player_count: int
    current_movie_title: str | None
    created_at: datetime


class ActiveEnvelope(BaseModel):
    active: LobbySummary | None


class CreateLobbyRequest(BaseModel):
    group_uuid: str | None = None
