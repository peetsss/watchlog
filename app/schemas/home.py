from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.auth import Viewer
from app.schemas.groups import GroupSummary, MovieSummary
from app.schemas.lobby import LobbySummary


class HomeCrews(BaseModel):
    count: int
    film_count: int
    watched_count: int


class HomeLogEntry(BaseModel):
    film_id: int
    group_id: UUID
    group_name: str
    movie: MovieSummary
    watched_at: datetime
    club_score: float | None
    score_count: int


class HomeFeaturedGroup(GroupSummary):
    up_next_count: int
    up_next: list[MovieSummary]
    last_watched: HomeLogEntry | None


class HomeResponse(BaseModel):
    viewer: Viewer
    active_lobby: LobbySummary | None
    crews: HomeCrews
    featured_group: HomeFeaturedGroup | None
    log: list[HomeLogEntry]
