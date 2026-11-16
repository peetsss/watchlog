from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MovieSearchResult(BaseModel):
    tmdb_id: int
    title: str
    year: str | None
    poster_url: str | None
    media_type: Literal["movie", "series"]
    movie_id: int | None = None


class MovieSearchEnvelope(BaseModel):
    movies: list[MovieSearchResult]


class MovieDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int | None
    imdb_id: str | None
    title: str
    original_title: str | None
    media_type: Literal["movie", "series"]
    description: str | None
    tagline: str | None
    status: str | None
    runtime: int | None
    release_date: date | None
    adult: bool
    genres: str | None
    keywords: str | None
    director: str | None
    writers: str | None
    actors: str | None
    country: str | None
    original_language: str | None
    spoken_languages: str | None
    production_companies: str | None
    poster_path: str | None
    backdrop_path: str | None
    awards: str | None
    revenue: int | None
    budget: int | None
    tmdb_score: float | None
    vote_count: int | None
    popularity: float | None
    imdb_score: float | None
    rottentomato_score: str | None
    metacritic_score: str | None
    filmweb_score: float | None
    imdb_url: str | None
    rottentomato_url: str | None
    metacritic_url: str | None
    filmweb_url: str | None
    homepage: str | None
    created_at: datetime
    updated_at: datetime
