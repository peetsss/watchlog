import logging

import httpx

from app.clients.tmdb import SyncTMDBWatchProviderClient, TMDBClient


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
