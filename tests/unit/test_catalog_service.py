from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.movie import Movie
from app.services.catalog import (
    discover_window,
    import_catalogue_items,
    iter_month_windows,
    latest_catalogue_date,
    should_import,
    split_window,
    sync_catalogue_range,
)

MOVIE_DETAILS = {
    "id": 11,
    "title": "A New Film",
    "status": "Released",
    "overview": "A fresh release.",
    "adult": False,
    "release_date": "2026-01-15",
}

SERIES_DETAILS = {
    "id": 21,
    "name": "A New Series",
    "status": "Returning Series",
    "overview": "A fresh series.",
    "adult": False,
    "first_air_date": "2026-01-10",
}


class FakeSyncClient:
    def __init__(self) -> None:
        self.discover_calls: list[tuple[str, date, date, int, int]] = []
        self.discover_payloads: dict[tuple[str, date, date, int], dict[str, object] | None] = {}
        self.details: dict[tuple[int, str], dict[str, object] | None] = {}

    def discover(
        self,
        media_type: str,
        start: date,
        end: date,
        page: int = 1,
        min_votes: int = 0,
    ) -> dict[str, object] | None:
        self.discover_calls.append((media_type, start, end, page, min_votes))
        return self.discover_payloads.get((media_type, start, end, page))

    def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        return self.details.get((tmdb_id, media_type))


def _item(tmdb_id: int, score: float = 7.0, votes: int = 10, popularity: float = 1.0) -> dict[str, object]:
    return {"id": tmdb_id, "vote_average": score, "vote_count": votes, "popularity": popularity}


def test_discover_window_paginates_and_dedupes() -> None:
    client = FakeSyncClient()
    client.discover_payloads = {
        ("movie", date(2026, 1, 1), date(2026, 1, 31), 1): {"total_pages": 2, "results": [_item(1), _item(2)]},
        ("movie", date(2026, 1, 1), date(2026, 1, 31), 2): {"total_pages": 2, "results": [_item(2), _item(3)]},
    }

    window = discover_window(client, "movie", date(2026, 1, 1), date(2026, 1, 31))

    assert window is not None
    assert [item["id"] for item in window.results] == [1, 2, 3]
    assert window.complete is True
    assert len(client.discover_calls) == 2


def test_discover_window_is_incomplete_when_total_pages_exceed_the_cap() -> None:
    client = FakeSyncClient()
    client.discover_payloads = {
        ("movie", date(2026, 1, 1), date(2026, 1, 31), 1): {"total_pages": 5, "results": [_item(1)]},
        ("movie", date(2026, 1, 1), date(2026, 1, 31), 2): {"total_pages": 5, "results": [_item(2)]},
    }

    window = discover_window(client, "movie", date(2026, 1, 1), date(2026, 1, 31), max_pages=2)

    assert window is not None
    assert [item["id"] for item in window.results] == [1, 2]
    assert window.complete is False


def test_discover_window_returns_none_when_the_first_page_fails() -> None:
    client = FakeSyncClient()

    assert discover_window(client, "movie", date(2026, 1, 1), date(2026, 1, 31)) is None


def test_sync_catalogue_range_splits_incomplete_windows(sync_session: Session) -> None:
    client = FakeSyncClient()
    client.discover_payloads = {
        ("movie", date(2026, 1, 1), date(2026, 1, 2), 1): {"total_pages": 2, "results": [_item(1)]},
        ("movie", date(2026, 1, 1), date(2026, 1, 1), 1): {"total_pages": 1, "results": [_item(1)]},
        ("movie", date(2026, 1, 2), date(2026, 1, 2), 1): {"total_pages": 1, "results": [_item(2)]},
    }
    client.details = {(1, "movie"): {**MOVIE_DETAILS, "id": 1}, (2, "movie"): {**MOVIE_DETAILS, "id": 2}}

    stats = sync_catalogue_range(
        sync_session,
        client,
        "movie",
        date(2026, 1, 1),
        date(2026, 1, 2),
        max_pages=1,
        refresh_existing=False,
    )

    assert stats.discovered == 2
    assert stats.inserted == 2
    assert ("movie", date(2026, 1, 1), date(2026, 1, 2), 1, 0) in client.discover_calls
    assert ("movie", date(2026, 1, 1), date(2026, 1, 1), 1, 0) in client.discover_calls
    assert ("movie", date(2026, 1, 2), date(2026, 1, 2), 1, 0) in client.discover_calls


def test_discover_window_passes_min_votes_to_the_client() -> None:
    client = FakeSyncClient()
    client.discover_payloads = {
        ("movie", date(2026, 1, 1), date(2026, 1, 31), 1): {"total_pages": 1, "results": []},
    }

    window = discover_window(client, "movie", date(2026, 1, 1), date(2026, 1, 31), min_votes=10)

    assert window is not None
    assert client.discover_calls == [("movie", date(2026, 1, 1), date(2026, 1, 31), 1, 10)]


def test_import_catalogue_items_inserts_released_and_skips_the_rest(sync_session: Session) -> None:
    client = FakeSyncClient()
    client.details = {
        (11, "movie"): MOVIE_DETAILS,
        (12, "movie"): {**MOVIE_DETAILS, "id": 12, "status": "Post Production"},
        (14, "movie"): {**MOVIE_DETAILS, "id": 14, "adult": True},
    }
    items = [_item(11), _item(12), _item(13), _item(14)]

    stats = import_catalogue_items(sync_session, client, "movie", items, refresh_existing=False)

    assert stats.discovered == 4
    assert stats.inserted == 1
    assert stats.skipped == 2
    assert stats.failed == 1
    movie = sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11, Movie.media_type == "movie"))
    assert movie is not None
    assert movie.title == "A New Film"


def test_import_catalogue_items_refreshes_existing_movies(sync_session: Session) -> None:
    sync_session.add(Movie(tmdb_id=11, title="Stale", media_type="movie", tmdb_score=5.0, vote_count=3, popularity=0.5))
    sync_session.commit()
    client = FakeSyncClient()

    stats = import_catalogue_items(
        sync_session,
        client,
        "movie",
        [_item(11, score=7.5, votes=100, popularity=9.0)],
        refresh_existing=True,
    )

    assert stats.discovered == 1
    assert stats.updated == 1
    assert stats.inserted == 0
    sync_session.expire_all()
    movie = sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11))
    assert movie is not None
    assert movie.tmdb_score == 7.5
    assert movie.vote_count == 100
    assert movie.popularity == 9.0


def test_import_catalogue_items_leaves_existing_movies_alone_without_refresh(sync_session: Session) -> None:
    sync_session.add(Movie(tmdb_id=11, title="Stale", media_type="movie", tmdb_score=5.0))
    sync_session.commit()
    client = FakeSyncClient()

    stats = import_catalogue_items(sync_session, client, "movie", [_item(11, score=7.5)], refresh_existing=False)

    assert stats.updated == 0
    sync_session.expire_all()
    movie = sync_session.scalar(select(Movie).where(Movie.tmdb_id == 11))
    assert movie is not None
    assert movie.tmdb_score == 5.0


def test_import_catalogue_items_accepts_series_statuses(sync_session: Session) -> None:
    client = FakeSyncClient()
    client.details = {
        (21, "series"): SERIES_DETAILS,
        (22, "series"): {**SERIES_DETAILS, "id": 22, "status": "Canceled"},
    }

    stats = import_catalogue_items(sync_session, client, "series", [_item(21), _item(22)], refresh_existing=False)

    assert stats.inserted == 1
    assert stats.skipped == 1


def test_should_import_rules() -> None:
    assert should_import(MOVIE_DETAILS, "movie") is True
    assert should_import({**MOVIE_DETAILS, "status": "Rumored"}, "movie") is False
    assert should_import({**MOVIE_DETAILS, "overview": ""}, "movie") is False
    assert should_import({**MOVIE_DETAILS, "adult": True}, "movie") is False
    assert should_import(SERIES_DETAILS, "series") is True
    assert should_import({**SERIES_DETAILS, "status": "Canceled"}, "series") is False


def test_iter_month_windows_covers_partial_months() -> None:
    windows = list(iter_month_windows(date(2026, 1, 15), date(2026, 3, 10)))

    assert windows == [
        (date(2026, 1, 15), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 10)),
    ]


def test_iter_month_windows_rejects_reversed_range() -> None:
    with pytest.raises(ValueError):
        list(iter_month_windows(date(2026, 2, 1), date(2026, 1, 1)))


def test_split_window_divides_the_range() -> None:
    left, right = split_window(date(2026, 1, 1), date(2026, 1, 2))

    assert left == (date(2026, 1, 1), date(2026, 1, 1))
    assert right == (date(2026, 1, 2), date(2026, 1, 2))
    with pytest.raises(ValueError):
        split_window(date(2026, 1, 1), date(2026, 1, 1))


def test_latest_catalogue_date_ignores_other_types_and_nulls(sync_session: Session) -> None:
    sync_session.add_all(
        [
            Movie(tmdb_id=1, title="Old", media_type="movie", release_date=date(2024, 1, 1)),
            Movie(tmdb_id=2, title="New", media_type="movie", release_date=date(2026, 5, 1)),
            Movie(tmdb_id=3, title="Series", media_type="series", release_date=date(2026, 6, 1)),
            Movie(tmdb_id=4, title="Undated", media_type="movie", release_date=None),
        ]
    )
    sync_session.commit()

    assert latest_catalogue_date(sync_session, "movie") == date(2026, 5, 1)
    assert latest_catalogue_date(sync_session, "series") == date(2026, 6, 1)
