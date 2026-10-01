import httpx
from django.conf import settings
from loguru import logger

POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str | None = None, language: str = "en-US", timeout: int = 10):
        self.api_key = api_key or settings.TMDB_API_KEY
        self.language = language
        self.client = httpx.Client(base_url=self.BASE_URL, timeout=timeout)

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict | None:
        params = dict(params or {})
        params.update({"api_key": self.api_key, "language": self.language})

        try:
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.exception("TMDB request to {} failed: {}", endpoint, e)
            return None

    def search(self, query: str) -> list[dict] | None:
        data = self._make_request("/search/multi", {"query": query})
        if data is None:
            return None

        results = [item for item in data.get("results", []) if item.get("media_type") in {"movie", "tv"}]
        return [
            {
                "id": item["id"],
                "title": item.get("title") or item.get("name") or "",
                "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
                "poster_url": POSTER_BASE_URL + item["poster_path"] if item.get("poster_path") else None,
                "media_type": "series" if item["media_type"] == "tv" else "movie",
            }
            for item in results
        ]

    def get_details(self, tmdb_id: int, media_type: str) -> dict | None:
        endpoint = f"/tv/{tmdb_id}" if media_type == "series" else f"/movie/{tmdb_id}"
        return self._make_request(endpoint, {"append_to_response": "credits,keywords,external_ids"})
