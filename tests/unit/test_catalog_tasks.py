from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.movie import Movie
from app.tasks.catalog import sync_recent_movies, sync_recent_series
from app.workers.runtime import dispose_worker_runtime, init_worker_runtime

MOVIE_DETAILS = {
    "id": 11,
    "title": "Fresh Release",
    "status": "Released",
    "overview": "A newly released film.",
    "adult": False,
    "release_date": "2026-11-20",
}

SERIES_DETAILS = {
    "id": 11,
    "name": "Fresh Series",
    "status": "Returning Series",
    "overview": "A newly premiered series.",
    "adult": False,
    "first_air_date": "2026-11-18",
}

DISCOVER_ITEM = {"id": 11, "vote_average": 7.2, "vote_count": 20, "popularity": 3.0}


class FakeSyncClient:
    def __init__(self, details_override: dict[str, object] | None = None) -> None:
        self.details_override = details_override
        self.windows: list[tuple[str, date, date, int]] = []

    def __enter__(self) -> FakeSyncClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def discover(
        self,
        media_type: str,
        start: date,
        end: date,
        page: int = 1,
        min_votes: int = 0,
    ) -> dict[str, object]:
        self.windows.append((media_type, start, end, min_votes))
        return {"total_pages": 1, "results": [DISCOVER_ITEM]}

    def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object]:
        if self.details_override is not None:
            return {**self.details_override, "id": tmdb_id}
        if media_type == "series":
            return {**SERIES_DETAILS, "id": tmdb_id}
        return {**MOVIE_DETAILS, "id": tmdb_id}


def _apply(
    task: object,
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    client: FakeSyncClient,
) -> dict[str, int]:
    monkeypatch.setattr("app.tasks.catalog.SyncTMDBClient", lambda **_: client)
    init_worker_runtime(test_settings)
    try:
        result = task.apply().get()
    finally:
        dispose_worker_runtime()
    sync_session.expire_all()
    return result


def test_sync_recent_movies_inserts_new_movies(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSyncClient()

    result = _apply(sync_recent_movies, sync_session, test_settings, monkeypatch, client)

    assert result == {"discovered": 1, "inserted": 1, "updated": 0, "skipped": 0, "failed": 0}
    movie = sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11, Movie.media_type == "movie"))
    assert movie is not None
    assert movie.title == "Fresh Release"
    today = datetime.now(UTC).date()
    assert client.windows == [("movie", today - timedelta(days=7), today, 0)]


def test_sync_recent_movies_refreshes_existing_rows(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_session.add(Movie(tmdb_id=11, title="Stale", media_type="movie", tmdb_score=5.0, vote_count=3, popularity=0.5))
    sync_session.commit()
    client = FakeSyncClient()

    result = _apply(sync_recent_movies, sync_session, test_settings, monkeypatch, client)

    assert result == {"discovered": 1, "inserted": 0, "updated": 1, "skipped": 0, "failed": 0}
    movie = sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11, Movie.media_type == "movie"))
    assert movie is not None
    assert movie.tmdb_score == 7.2
    assert movie.vote_count == 20
    assert movie.popularity == 3.0


def test_sync_recent_series_inserts_series(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSyncClient()

    result = _apply(sync_recent_series, sync_session, test_settings, monkeypatch, client)

    assert result["inserted"] == 1
    series = sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11, Movie.media_type == "series"))
    assert series is not None
    assert series.title == "Fresh Series"
    assert series.release_date == date(2026, 11, 18)


def test_sync_recent_skips_unreleased_titles(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSyncClient(details_override={**MOVIE_DETAILS, "status": "Post Production"})

    result = _apply(sync_recent_movies, sync_session, test_settings, monkeypatch, client)

    assert result == {"discovered": 1, "inserted": 0, "updated": 0, "skipped": 1, "failed": 0}
    assert sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11, Movie.media_type == "movie")) is None


def test_sync_recent_passes_the_vote_threshold_from_settings(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSyncClient()
    settings = test_settings.model_copy(update={"tmdb_sync_min_vote_count": 5})
    monkeypatch.setattr("app.tasks.catalog.SyncTMDBClient", lambda **_: client)
    monkeypatch.setattr("app.tasks.catalog.get_settings", lambda: settings)
    init_worker_runtime(test_settings)
    try:
        sync_recent_movies.apply().get()
    finally:
        dispose_worker_runtime()

    assert len(client.windows) == 1
    media_type, start, end, min_votes = client.windows[0]
    assert media_type == "movie"
    assert min_votes == 5
