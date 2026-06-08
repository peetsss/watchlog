import httpx
from django.conf import settings
from loguru import logger


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str | None = None, language: str = "en-US", timeout: int = 10):
        self.api_key = api_key or getattr(settings, "TMDB_API_KEY", None)
        self.language = language
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=timeout)

    async def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        params = params.copy() if params else {}
        params.update({"api_key": self.api_key, "language": self.language})

        try:
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.exception(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.exception(f"Request Error: {e}")
            raise

    async def get_movie_details(self, movie_id: int, append_to_response: str | None = None) -> dict:
        params = {}
        if append_to_response:
            params["append_to_response"] = append_to_response
        return await self._make_request(f"/movie/{movie_id}", params=params)

    async def search_movie(self, query: str, page: int = 1) -> dict:
        return await self._make_request("/search/movie", params={"query": query, "page": page})

    async def get_popular_movies(self, page: int = 1) -> dict:
        return await self._make_request("/movie/popular", params={"page": page})

    async def get_tv_details(self, tv_id: int, append_to_response: str | None = None) -> dict:
        params = {}
        if append_to_response:
            params["append_to_response"] = append_to_response
        return await self._make_request(f"/tv/{tv_id}", params=params)

    async def aclose(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
