import unittest
from unittest.mock import MagicMock, patch

from src.movies.utils.imdb import IMDbClient


class TestIMDbClient(unittest.TestCase):
    @patch("src.movies.utils.imdb.requests.get")
    def test_fetch_search_query_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Search": [
                {
                    "Title": "The Strangers",
                    "Year": "2008",
                    "imdbID": "tt0482606",
                    "Type": "movie",
                },
                {
                    "Title": "The Strangers: Prey at Night",
                    "Year": "2018",
                    "imdbID": "tt1285009",
                    "Type": "movie",
                },
                {
                    "Title": "The Strangers: Chapter 1",
                    "Year": "2024",
                    "imdbID": "tt22050754",
                    "Type": "series",
                },
                {
                    "Title": "The Strangers",
                    "Year": "2137",
                    "imdbID": "tt4206669",
                    "Type": "game",
                },
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        results = IMDbClient.fetch_search_query("The Strangers")

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["Title"], "The Strangers")
        self.assertEqual(results[1]["Title"], "The Strangers: Prey at Night")
        self.assertEqual(results[2]["Title"], "The Strangers: Chapter 1")

    @patch("src.movies.utils.imdb.requests.get")
    def test_fetch_search_query_failure(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        results = IMDbClient.fetch_search_query("The Strangers")

        self.assertEqual(results, [])

    @patch("src.movies.utils.imdb.requests.get")
    def test_fetch_movie_details_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Title": "Avengers: Endgame",
            "Year": "2019",
            "imdbID": "tt4154796",
            "Type": "movie",
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = IMDbClient.fetch_movie_details("tt4154796")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["Title"], "Avengers: Endgame")
        self.assertEqual(result["Year"], "2019")
        self.assertEqual(result["imdbID"], "tt4154796")

    @patch("src.movies.utils.imdb.requests.get")
    def test_fetch_movie_details_failure(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = None
        mock_get.return_value = mock_response

        result = IMDbClient.fetch_movie_details("tt213769420")

        self.assertIsNone(result)
