import logging
from datetime import date

import httpx
import pytest

from app.clients.tmdb import (
    RateLimiter,
    SyncTMDBClient,
    SyncTMDBWatchProviderClient,
    TMDBClient,
    _parse_retry_after,
)


async def test_search_maps_movies_and_series() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "Dune"
        assert request.url.params["api_key"] == "key"
        assert request.url.params["language"] == "en-US"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 438631,
                        "title": "Dune",
                        "release_date": "2021-10-22",
                        "poster_path": "/dune.jpg",
                        "media_type": "movie",
                    },
                    {
                        "id": 1399,
                        "name": "Game of Thrones",
                        "first_air_date": "2011-04-17",
                        "poster_path": None,
                        "media_type": "tv",
                    },
                    {"id": 1, "name": "A Person", "media_type": "person"},
                ]
            },
        )

    async with TMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        results = await client.search("Dune")

    assert results is not None
    assert len(results) == 2
    assert results[0].tmdb_id == 438631
    assert results[0].title == "Dune"
    assert results[0].year == "2021"
    assert results[0].media_type == "movie"
    assert results[0].poster_url == "https://image.tmdb.org/t/p/w500/dune.jpg"
    assert results[1].media_type == "series"
    assert results[1].year == "2011"
    assert results[1].poster_url is None


async def test_search_returns_none_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"status_message": "boom"})

    async with TMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        assert await client.search("Dune") is None


async def test_access_token_uses_bearer_and_omits_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer v4-secret"
        assert "api_key" not in request.url.params
        assert request.url.params["language"] == "en-US"
        return httpx.Response(200, json={"results": []})

    async with TMDBClient(
        api_key="v3-secret",
        access_token="v4-secret",
        transport=httpx.MockTransport(handler),
    ) as client:
        assert await client.search("Dune") == []


async def test_http_error_does_not_log_the_api_key(caplog) -> None:
    caplog.set_level(logging.ERROR)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"status_message": "boom"})

    async with TMDBClient(api_key="super-secret-key", transport=httpx.MockTransport(handler)) as client:
        assert await client.search("Dune") is None

    assert "super-secret-key" not in caplog.text
    assert "HTTP 500" in caplog.text


def test_sync_client_uses_the_access_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer v4-secret"
        assert "api_key" not in request.url.params
        return httpx.Response(200, json={"results": {}})

    with SyncTMDBWatchProviderClient(
        api_key="v3-secret",
        access_token="v4-secret",
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.get_watch_providers(1, "movie") == {"results": {}}


async def test_get_details_uses_the_media_type_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/3/movie/438631"
        assert request.url.params["append_to_response"] == "credits,keywords,external_ids"
        return httpx.Response(200, json={"id": 438631, "title": "Dune"})

    async with TMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        details = await client.get_details(438631, "movie")

    assert details == {"id": 438631, "title": "Dune"}


async def test_get_details_uses_the_tv_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/3/tv/1399"
        return httpx.Response(200, json={"id": 1399, "name": "Game of Thrones"})

    async with TMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        details = await client.get_details(1399, "series")

    assert details == {"id": 1399, "name": "Game of Thrones"}


async def test_non_object_payload_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with TMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        assert await client.search("Dune") is None


def test_rate_limiter_paces_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 0.0}
    slept: list[float] = []
    monkeypatch.setattr("app.clients.tmdb.time.monotonic", lambda: clock["now"])

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("app.clients.tmdb.time.sleep", fake_sleep)
    limiter = RateLimiter(requests_per_second=2.0)

    limiter.wait()
    limiter.wait()

    assert slept == [0.5]


def test_rate_limiter_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(requests_per_second=0.0)


def test_sync_discover_uses_the_movie_window_and_ordering() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert request.url.path == "/3/discover/movie"
        assert params["primary_release_date.gte"] == "2026-01-01"
        assert params["primary_release_date.lte"] == "2026-01-31"
        assert params["sort_by"] == "primary_release_date.asc"
        assert params["include_adult"] == "false"
        assert params["page"] == "1"
        return httpx.Response(200, json={"results": [], "total_pages": 0})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        payload = client.discover("movie", date(2026, 1, 1), date(2026, 1, 31))

    assert payload == {"results": [], "total_pages": 0}


def test_sync_discover_uses_the_tv_window_and_ordering() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert request.url.path == "/3/discover/tv"
        assert params["first_air_date.gte"] == "2026-01-01"
        assert params["first_air_date.lte"] == "2026-01-31"
        assert params["sort_by"] == "first_air_date.asc"
        return httpx.Response(200, json={"results": [], "total_pages": 0})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        payload = client.discover("series", date(2026, 1, 1), date(2026, 1, 31))

    assert payload == {"results": [], "total_pages": 0}


def test_sync_discover_rejects_unknown_media_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            client.discover("podcast", date(2026, 1, 1), date(2026, 1, 2))


def test_sync_discover_includes_the_vote_threshold_when_set() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["vote_count.gte"] == "10"
        return httpx.Response(200, json={"results": [], "total_pages": 0})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        payload = client.discover("movie", date(2026, 1, 1), date(2026, 1, 31), min_votes=10)

    assert payload == {"results": [], "total_pages": 0}


def test_sync_discover_omits_the_vote_filter_by_default() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "vote_count.gte" not in request.url.params
        return httpx.Response(200, json={"results": [], "total_pages": 0})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        client.discover("movie", date(2026, 1, 1), date(2026, 1, 31))


def test_sync_discover_rejects_negative_min_votes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            client.discover("movie", date(2026, 1, 1), date(2026, 1, 2), min_votes=-1)


def test_sync_get_details_uses_the_media_type_endpoints() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path in {"/3/movie/42", "/3/tv/42"}
        assert request.url.params["append_to_response"] == "credits,keywords,external_ids"
        return httpx.Response(200, json={"id": 42})

    with SyncTMDBClient(api_key="key", transport=httpx.MockTransport(handler)) as client:
        assert client.get_details(42, "movie") == {"id": 42}
        assert client.get_details(42, "series") == {"id": 42}


def test_sync_client_retries_after_throttle_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"results": [{"id": 1}]})

    monkeypatch.setattr("app.clients.tmdb.time.sleep", lambda seconds: sleeps.append(seconds))

    with SyncTMDBClient(api_key="key", requests_per_second=1000, transport=httpx.MockTransport(handler)) as client:
        payload = client.discover("movie", date(2026, 1, 1), date(2026, 1, 2))

    assert attempts == 2
    assert payload == {"results": [{"id": 1}]}
    assert sleeps[0] == 2.0


def test_sync_client_throttle_without_retry_after_uses_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(409)
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.clients.tmdb.time.sleep", lambda seconds: sleeps.append(seconds))

    with SyncTMDBClient(api_key="key", requests_per_second=1000, transport=httpx.MockTransport(handler)) as client:
        payload = client.discover("movie", date(2026, 1, 1), date(2026, 1, 2))

    assert attempts == 2
    assert payload == {"results": []}
    assert sleeps[0] == 1.0


def test_sync_client_gives_up_after_repeated_throttles(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"Retry-After": "1"})

    monkeypatch.setattr("app.clients.tmdb.time.sleep", lambda seconds: None)

    with SyncTMDBClient(api_key="key", requests_per_second=1000, transport=httpx.MockTransport(handler)) as client:
        assert client.get_details(1, "movie") is None

    assert attempts == 3


def test_sync_client_retries_on_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"id": 1})

    monkeypatch.setattr("app.clients.tmdb.time.sleep", lambda seconds: sleeps.append(seconds))

    with SyncTMDBClient(api_key="key", requests_per_second=1000, transport=httpx.MockTransport(handler)) as client:
        assert client.get_details(1, "movie") == {"id": 1}

    assert attempts == 2
    assert sleeps[0] == 1.0


def test_parse_retry_after_handles_seconds_and_dates() -> None:
    assert _parse_retry_after("5") == 5.0
    assert _parse_retry_after("0") == 0.0
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("") is None
    assert _parse_retry_after("not-a-date") is None
    assert _parse_retry_after("Tue, 01 Jan 2000 00:00:00 GMT") == 0.0
