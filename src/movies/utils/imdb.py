import logging
from typing import Any

import requests
from django.conf import settings

from .request_limiter import request_limiter


class IMDbClient:
    url = "https://movie-database-alternative.p.rapidapi.com/"
    headers = {
        "x-rapidapi-key": settings.RAPIDAPI_MOVIE_DB_KEY,
        "x-rapidapi-host": settings.RAPIDAPI_MOVIE_DB_HOST,
    }

    @staticmethod
    def make_request(params=None) -> dict[str, Any] | Exception:
        if request_limiter.can_make_request():
            response = requests.get(IMDbClient.url, headers=IMDbClient.headers, params=params)
            response.raise_for_status()
            response_json = response.json()
            return response_json
        raise Exception("Request limit reached. Cannot make more requests today.")

    @staticmethod
    def _fetch(querystring=None) -> dict[str, Any] | None:
        try:
            data = IMDbClient.make_request(params=querystring)
            return data
        except Exception as e:
            logging.critical(e)
            return None

    @staticmethod
    def fetch_search_query(query: str) -> list[dict[str, Any]] | None:
        data = IMDbClient._fetch({"s": query, "r": "json"})
        if data is None:
            return None
        filtered_results = [item for item in data.get("Search", []) if item.get("Type") in {"movie", "series"}]
        return filtered_results

    @staticmethod
    def fetch_movie_details(movie_id: str) -> list[dict[str, Any]] | None:
        return IMDbClient._fetch({"r": "json", "i": movie_id})
