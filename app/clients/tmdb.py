import logging

import httpx

from app.schemas.movies import MovieSearchResult

logger = logging.getLogger(__name__)

POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(
        self,
        api_key: str,
        language: str = "en-US",
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._language = language
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=timeout, transport=transport)

    async def __aenter__(self) -> TMDBClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, endpoint: str, params: dict[str, object] | None = None) -> dict[str, object] | None:
        query = dict(params or {})
        query.update({"api_key": self._api_key, "language": self._language})
        try:
            response = await self._client.get(endpoint, params=query)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("TMDB request to %s failed", endpoint)
            return None

        payload = response.json()
        if not isinstance(payload, dict):
            logger.warning("TMDB returned a non-object payload for %s", endpoint)
            return None
        return payload

    async def search(self, query: str) -> list[MovieSearchResult] | None:
        data = await self._get("/search/multi", {"query": query})
        if data is None:
            return None

        results: list[MovieSearchResult] = []
        for item in _as_list(data.get("results")):
            if not isinstance(item, dict):
                continue
            item_type = _as_str(item.get("media_type"))
            if item_type not in {"movie", "tv"}:
                continue
            tmdb_id = _as_int(item.get("id"))
            if tmdb_id is None:
                continue
            release_date = _as_str(item.get("release_date")) or _as_str(item.get("first_air_date")) or ""
            poster_path = _as_str(item.get("poster_path"))
            results.append(
                MovieSearchResult(
                    tmdb_id=tmdb_id,
                    title=_as_str(item.get("title")) or _as_str(item.get("name")) or "",
                    year=release_date[:4] or None,
                    poster_url=f"{POSTER_BASE_URL}{poster_path}" if poster_path else None,
                    media_type="series" if item_type == "tv" else "movie",
                )
            )
        return results

    async def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        endpoint = f"/tv/{tmdb_id}" if media_type == "series" else f"/movie/{tmdb_id}"
        return await self._get(endpoint, {"append_to_response": "credits,keywords,external_ids"})
