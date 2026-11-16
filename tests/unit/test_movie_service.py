import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.schemas.movies import MovieSearchResult
from app.services.movies import attach_local_ids, get_or_create_movie

DETAILS: dict[str, object] = {
    "id": 438631,
    "title": "Dune",
    "overview": "A noble family becomes embroiled in a war.",
    "release_date": "2021-10-22",
    "genres": [{"name": "Science Fiction"}],
}


class FakeTMDB:
    def __init__(self, details: dict[str, object] | None) -> None:
        self.details = details
        self.calls: list[tuple[int, str]] = []

    async def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        self.calls.append((tmdb_id, media_type))
        return self.details


async def test_get_or_create_movie_creates_once(db_session: AsyncSession) -> None:
    client = FakeTMDB(DETAILS)

    movie = await get_or_create_movie(db_session, 438631, "movie", client)
    again = await get_or_create_movie(db_session, 438631, "movie", client)

    assert movie.id is not None
    assert movie.title == "Dune"
    assert again.id == movie.id
    assert client.calls == [(438631, "movie")]


async def test_get_or_create_movie_rejects_unknown_media_type(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="Unsupported media type"):
        await get_or_create_movie(db_session, 438631, "podcast", FakeTMDB(DETAILS))


async def test_get_or_create_movie_reports_tmdb_failure(db_session: AsyncSession) -> None:
    with pytest.raises(AppError) as exc_info:
        await get_or_create_movie(db_session, 438631, "movie", FakeTMDB(None))

    assert exc_info.value.code == "tmdb_unavailable"
    assert exc_info.value.status_code == 502


async def test_attach_local_ids(db_session: AsyncSession) -> None:
    movie = await get_or_create_movie(db_session, 438631, "movie", FakeTMDB(DETAILS))
    results = [
        MovieSearchResult(tmdb_id=438631, title="Dune", year="2021", poster_url=None, media_type="movie"),
        MovieSearchResult(tmdb_id=999, title="Unknown", year=None, poster_url=None, media_type="movie"),
    ]

    attached = await attach_local_ids(db_session, results)

    assert attached[0].movie_id == movie.id
    assert attached[1].movie_id is None
