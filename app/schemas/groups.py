from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GroupMember(BaseModel):
    id: int
    username: str
    initials: str
    color: str
    role: Literal["admin", "member"]


class GroupSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    member_count: int
    film_count: int
    members: list[GroupMember]


class GroupList(BaseModel):
    groups: list[GroupSummary]


class GroupPreview(BaseModel):
    id: UUID
    name: str
    description: str | None
    member_count: int
    film_count: int
    is_member: bool


class GroupDetail(GroupSummary):
    created_at: datetime


class MovieSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int | None
    title: str
    release_date: date | None
    runtime: int | None
    genres: str | None
    director: str | None
    description: str | None
    poster_path: str | None
    backdrop_path: str | None


class GroupFilm(BaseModel):
    id: int
    movie: MovieSummary
    status: Literal["up_next", "watched"]
    added_at: datetime
    added_by: str | None
    club_score: float | None
    score_count: int
    your_score: float | None


class GroupFilmList(BaseModel):
    films: list[GroupFilm]


class MemberScore(BaseModel):
    user_id: int
    username: str
    initials: str
    color: str
    score: float


class GroupFilmScores(BaseModel):
    film_id: int
    scores: list[MemberScore]


class MemberScoreStats(BaseModel):
    user_id: int
    username: str
    score_count: int
    average_score: float | None


class GroupStats(BaseModel):
    film_count: int
    watched_count: int
    up_next_count: int
    member_count: int
    average_score: float | None
    member_scores: list[MemberScoreStats]


class CreateGroupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)


class AddFilmRequest(BaseModel):
    tmdb_id: int = Field(gt=0)
    media_type: Literal["movie", "series"] = "movie"


class ScoreRequest(BaseModel):
    score: float = Field(ge=1, le=10)


class FilmStatusRequest(BaseModel):
    status: Literal["up_next", "watched"]


class InviteLinkResponse(BaseModel):
    invite_link: str
