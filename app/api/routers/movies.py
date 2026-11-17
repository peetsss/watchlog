from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import CurrentUser, LobbyViewer, SettingsDep, TMDBDep
from app.core.db import SessionDep
from app.core.errors import AppError
from app.core.rate_limit import rate_limit
from app.models.movie import Movie
from app.schemas.movies import MovieDetail, MovieSearchEnvelope
from app.services.movies import attach_local_ids
from app.services.watch_providers import get_watch_availability

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get(
    "/search",
    response_model=MovieSearchEnvelope,
    dependencies=[Depends(rate_limit("movies.search", 60, 60, scope="viewer"))],
)
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


@router.get(
    "/{movie_id}",
    response_model=MovieDetail,
    dependencies=[Depends(rate_limit("movies.detail", 60, 60, scope="viewer"))],
)
async def get_movie(
    movie_id: Annotated[int, Path(ge=1)],
    viewer: LobbyViewer,
    db: SessionDep,
    settings: SettingsDep,
    tmdb: TMDBDep,
) -> MovieDetail:
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise AppError("Movie not found.", code="not_found", status_code=404)
    region = viewer.user.region if viewer.user is not None else settings.default_region
    watch = await get_watch_availability(
        db,
        movie,
        region,
        settings.watch_provider_ttl_seconds,
        tmdb,
    )
    return MovieDetail.model_validate(movie).model_copy(update={"watch": watch})
