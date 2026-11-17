from collections.abc import Callable
from datetime import date

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_tmdb_client
from app.schemas.movies import MovieSearchResult
from tests.api.helpers import register_member


class FakeTMDB:
    def __init__(
        self,
        results: list[MovieSearchResult] | None,
        watch_payload: dict[str, object] | None = None,
    ) -> None:
        self.results = results
        self.watch_payload = watch_payload

    async def search(self, query: str) -> list[MovieSearchResult] | None:
        return self.results

    async def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        return None

    async def get_watch_providers(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        return self.watch_payload


WATCH_PAYLOAD = {
    "results": {
        "PL": {
            "link": "https://www.themoviedb.org/movie/438631/watch?locale=PL",
            "flatrate": [
                {
                    "provider_id": 8,
                    "provider_name": "Netflix",
                    "logo_path": "/netflix.jpg",
                    "display_priority": 1,
                }
            ],
            "rent": [
                {
                    "provider_id": 2,
                    "provider_name": "Apple TV",
                    "logo_path": "/apple.jpg",
                    "display_priority": 1,
                }
            ],
        }
    }
}

SEARCH_RESULTS = [
    MovieSearchResult(
        tmdb_id=438631,
        title="Dune",
        year="2021",
        poster_url="https://image.tmdb.org/t/p/w500/dune.jpg",
        media_type="movie",
    ),
    MovieSearchResult(
        tmdb_id=999,
        title="Another Movie",
        year="2020",
        poster_url=None,
        media_type="movie",
    ),
]


async def test_search_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/movies/search", params={"q": "Dune"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_search_returns_results_and_local_ids(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    movie_id = movie_factory(tmdb_id=438631, title="Dune", description="A noble family at war.")
    app.dependency_overrides[get_tmdb_client] = lambda: FakeTMDB(SEARCH_RESULTS)

    response = await client.get("/api/movies/search", params={"q": "Dune"})

    assert response.status_code == 200
    movies = response.json()["movies"]
    assert len(movies) == 2
    assert movies[0]["tmdb_id"] == 438631
    assert movies[0]["title"] == "Dune"
    assert movies[0]["movie_id"] == movie_id
    assert movies[1]["movie_id"] is None


async def test_search_returns_502_when_tmdb_fails(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    app.dependency_overrides[get_tmdb_client] = lambda: FakeTMDB(None)

    response = await client.get("/api/movies/search", params={"q": "Dune"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "tmdb_unavailable"


async def test_search_validates_the_query(client: AsyncClient) -> None:
    await register_member(client)

    response = await client.get("/api/movies/search", params={"q": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_movie_detail(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    movie_id = movie_factory(
        tmdb_id=438631,
        title="Dune",
        description="A noble family at war.",
        release_date=date(2021, 10, 22),
        runtime=155,
        genres="Science Fiction",
    )
    app.dependency_overrides[get_tmdb_client] = lambda: FakeTMDB([], None)

    response = await client.get(f"/api/movies/{movie_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == movie_id
    assert body["title"] == "Dune"
    assert body["release_date"] == "2021-10-22"
    assert body["runtime"] == 155
    assert body["watch"] is None
    assert "embeddings" not in body


async def test_movie_detail_loads_and_caches_watch_availability(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    movie_id = movie_factory(tmdb_id=438631, title="Dune")
    app.dependency_overrides[get_tmdb_client] = lambda: FakeTMDB([], WATCH_PAYLOAD)

    response = await client.get(f"/api/movies/{movie_id}")

    assert response.status_code == 200
    watch = response.json()["watch"]
    assert watch["region"] == "PL"
    assert watch["link"] == "https://www.themoviedb.org/movie/438631/watch?locale=PL"
    assert watch["stale"] is False
    assert [provider["name"] for provider in watch["offers"]["flatrate"]] == ["Netflix"]
    assert watch["offers"]["flatrate"][0]["logo_url"] == "https://image.tmdb.org/t/p/w92/netflix.jpg"
    assert [provider["name"] for provider in watch["offers"]["rent"]] == ["Apple TV"]


async def test_movie_detail_requires_authentication(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    movie_id = movie_factory(tmdb_id=1, title="Dune")

    response = await client.get(f"/api/movies/{movie_id}")

    assert response.status_code == 401


async def test_movie_detail_returns_404(client: AsyncClient) -> None:
    await register_member(client)

    response = await client.get("/api/movies/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
