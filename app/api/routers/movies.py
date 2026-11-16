from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import CurrentUser, TMDBDep
from app.core.db import SessionDep
from app.core.errors import AppError
from app.models.movie import Movie
from app.schemas.movies import MovieDetail, MovieSearchEnvelope
from app.services.movies import attach_local_ids

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("/search", response_model=MovieSearchEnvelope)
async def search_movies(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    _user: CurrentUser,
    db: SessionDep,
    tmdb: TMDBDep,
) -> MovieSearchEnvelope:
    results = await tmdb.search(q)
    if results is None:
        raise AppError("TMDB request failed.", code="tmdb_unavailable", status_code=502)
    return MovieSearchEnvelope(movies=await attach_local_ids(db, results))


@router.get("/{movie_id}", response_model=MovieDetail)
async def get_movie(
    movie_id: Annotated[int, Path(ge=1)],
    _user: CurrentUser,
    db: SessionDep,
) -> Movie:
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise AppError("Movie not found.", code="not_found", status_code=404)
    return movie
