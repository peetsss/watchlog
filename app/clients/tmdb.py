import logging
import threading
import time
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Final

import httpx

from app.schemas.movies import MovieSearchResult

logger = logging.getLogger(__name__)

POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"

MAX_ATTEMPTS: Final[int] = 3
BASE_BACKOFF_SECONDS: Final[float] = 1.0
MAX_BACKOFF_SECONDS: Final[float] = 60.0
THROTTLE_STATUS_CODES: Final[frozenset[int]] = frozenset({409, 429})


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


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _auth(api_key: str, access_token: str, language: str) -> tuple[dict[str, str], dict[str, object]]:
    headers: dict[str, str] = {}
    query: dict[str, object] = {"language": language}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        query["api_key"] = api_key
    return headers, query


class RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError(f"requests_per_second must be positive, got {requests_per_second}")
        self._interval = 1.0 / requests_per_second
        self._lock = threading.Lock()
        self._next_allowed = time.monotonic()

    def wait(self) -> None:
        with self._lock:
            delay = self._next_allowed - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._next_allowed = time.monotonic() + self._interval


def _parse_retry_after(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return max(float(text), 0.0)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except TypeError, ValueError, OverflowError:
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max((parsed - datetime.now(UTC)).total_seconds(), 0.0)


def _backoff_seconds(attempt: int) -> float:
    return min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)


def _sync_get(
    client: httpx.Client,
    endpoint: str,
    params: dict[str, object] | None,
    headers: dict[str, str],
    limiter: RateLimiter,
) -> dict[str, object] | None:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        limiter.wait()
        try:
            response = client.get(endpoint, params=params, headers=headers)
        except httpx.HTTPError as exc:
            logger.error("TMDB request to %s failed: %s", endpoint, type(exc).__name__)
            return None
        if response.status_code in THROTTLE_STATUS_CODES:
            delay = _parse_retry_after(response.headers.get("retry-after")) or _backoff_seconds(attempt)
            logger.warning("TMDB throttled %s (HTTP %s); waiting %s seconds", endpoint, response.status_code, delay)
            if attempt < MAX_ATTEMPTS:
                time.sleep(delay)
                continue
            return None
        if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
            delay = _backoff_seconds(attempt)
            logger.warning(
                "TMDB server error on %s (HTTP %s); waiting %s seconds", endpoint, response.status_code, delay
            )
            time.sleep(delay)
            continue
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error("TMDB request to %s failed with HTTP %s", endpoint, response.status_code)
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            logger.warning("TMDB returned a non-object payload for %s", endpoint)
            return None
        return payload
    return None


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(
        self,
        api_key: str,
        access_token: str = "",
        language: str = "en-US",
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._access_token = access_token
        self._language = language
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=timeout, transport=transport)

    async def __aenter__(self) -> TMDBClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, endpoint: str, params: dict[str, object] | None = None) -> dict[str, object] | None:
        headers, auth_query = _auth(self._api_key, self._access_token, self._language)
        query = dict(params or {})
        query.update(auth_query)
        try:
            response = await self._client.get(endpoint, params=query, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("TMDB request to %s failed with HTTP %s", endpoint, exc.response.status_code)
            return None
        except httpx.HTTPError as exc:
            logger.error("TMDB request to %s failed: %s", endpoint, type(exc).__name__)
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
                    overview=_as_str(item.get("overview")),
                    tmdb_score=_as_float(item.get("vote_average")),
                )
            )
        return results

    async def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        endpoint = f"/tv/{tmdb_id}" if media_type == "series" else f"/movie/{tmdb_id}"
        return await self._get(endpoint, {"append_to_response": "credits,keywords,external_ids"})

    async def get_watch_providers(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        endpoint = f"/tv/{tmdb_id}/watch/providers" if media_type == "series" else f"/movie/{tmdb_id}/watch/providers"
        return await self._get(endpoint)


class _SyncTMDBBase:
    def __init__(
        self,
        api_key: str,
        access_token: str = "",
        language: str = "en-US",
        timeout: float = 10.0,
        requests_per_second: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._headers, self._auth_query = _auth(api_key, access_token, language)
        self._limiter = RateLimiter(requests_per_second)
        self._client = httpx.Client(base_url=TMDBClient.BASE_URL, timeout=timeout, transport=transport)

    def __enter__(self) -> _SyncTMDBBase:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get(self, endpoint: str, params: dict[str, object] | None = None) -> dict[str, object] | None:
        query = dict(params or {})
        query.update(self._auth_query)
        return _sync_get(self._client, endpoint, query, self._headers, self._limiter)


class SyncTMDBWatchProviderClient(_SyncTMDBBase):
    def get_watch_providers(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        endpoint = f"/tv/{tmdb_id}/watch/providers" if media_type == "series" else f"/movie/{tmdb_id}/watch/providers"
        return self._get(endpoint)


class SyncTMDBClient(_SyncTMDBBase):
    def discover(self, media_type: str, start: date, end: date, page: int = 1) -> dict[str, object] | None:
        if media_type not in {"movie", "series"}:
            raise ValueError(f"Unsupported media type: {media_type}")
        if page < 1:
            raise ValueError(f"page must be at least 1, got {page}")
        date_field = "first_air_date" if media_type == "series" else "primary_release_date"
        endpoint = "/discover/tv" if media_type == "series" else "/discover/movie"
        params: dict[str, object] = {
            f"{date_field}.gte": start.isoformat(),
            f"{date_field}.lte": end.isoformat(),
            "sort_by": f"{date_field}.asc",
            "include_adult": False,
            "page": page,
        }
        return self._get(endpoint, params)

    def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        if media_type not in {"movie", "series"}:
            raise ValueError(f"Unsupported media type: {media_type}")
        endpoint = f"/tv/{tmdb_id}" if media_type == "series" else f"/movie/{tmdb_id}"
        return self._get(endpoint, {"append_to_response": "credits,keywords,external_ids"})
