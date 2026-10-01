from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from groups.models import Group, GroupMovie

from ..models import Movie

User = get_user_model()

TMDB_MOVIE_DETAILS = {
    "id": 438631,
    "title": "Dune",
    "original_title": "Dune",
    "overview": "A noble family becomes embroiled in a war.",
    "status": "Released",
    "runtime": 155,
    "release_date": "2021-10-22",
    "adult": False,
    "genres": [{"id": 878, "name": "Science Fiction"}, {"id": 12, "name": "Adventure"}],
    "poster_path": "/d5vxZgWJJcpLfPtHnOJmsPfUCBq.jpg",
    "backdrop_path": "/jYoe5UywHmS4xtQ7dgyLIzLuWxc.jpg",
    "vote_average": 7.8,
    "revenue": 1083300000,
    "budget": 165000000,
    "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
    "credits": {
        "crew": [
            {"name": "Denis Villeneuve", "job": "Director"},
            {"name": "Jon Spaihts", "job": "Screenplay"},
        ],
        "cast": [{"name": "Timothée Chalamet"}, {"name": "Rebecca Ferguson"}],
    },
    "keywords": {"keywords": [{"name": "desert"}, {"name": "space war"}]},
    "external_ids": {"imdb_id": "tt11604119"},
}


class MovieViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.group = Group.objects.create(name="Test Group")
        self.client.login(username="testuser", password="password")

    @patch("movies.views.TMDBClient.search")
    def test_search_movies(self, mock_search):
        mock_search.return_value = [
            {
                "id": 438631,
                "title": "Dune",
                "year": "2021",
                "poster_url": "https://image.tmdb.org/t/p/w500/d5vxZgWJJcpLfPtQ7dgyLIzLuWxc.jpg",
                "media_type": "movie",
            }
        ]
        response = self.client.post(reverse("search_movies"), {"query": "Dune"})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "movies": [
                    {
                        "id": 438631,
                        "title": "Dune",
                        "year": "2021",
                        "poster_url": "https://image.tmdb.org/t/p/w500/d5vxZgWJJcpLfPtQ7dgyLIzLuWxc.jpg",
                        "media_type": "movie",
                    }
                ]
            },
        )

    @patch("movies.views.TMDBClient.search")
    def test_search_movies_api_failure(self, mock_search):
        mock_search.return_value = None
        response = self.client.post(reverse("search_movies"), {"query": "Dune"})
        self.assertEqual(response.status_code, 502)
        self.assertJSONEqual(response.content, {"error": "TMDB request failed."})

    @patch("movies.views.TMDBClient.get_details")
    def test_add_movie(self, mock_get_details):
        mock_get_details.return_value = TMDB_MOVIE_DETAILS

        response = self.client.post(
            reverse("add_movie"),
            {"movie_id": "438631", "media_type": "movie", "group_uuid": str(self.group.uuid)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"msg": "Dune has been added to Test Group"})

        movie = Movie.objects.get(tmdb_id=438631)
        self.assertEqual(movie.title, "Dune")
        self.assertEqual(movie.imdb_id, "tt11604119")
        self.assertEqual(movie.media_type, Movie.MediaType.MOVIE)
        self.assertEqual(movie.release_date, date(2021, 10, 22))
        self.assertEqual(movie.runtime, 155)
        self.assertEqual(movie.genres, "Science Fiction, Adventure")
        self.assertEqual(movie.director, "Denis Villeneuve")
        self.assertEqual(movie.writers, "Jon Spaihts")
        self.assertEqual(movie.actors, "Timothée Chalamet, Rebecca Ferguson")
        self.assertEqual(movie.country, "United States of America")
        self.assertEqual(movie.keywords, "desert, space war")
        self.assertEqual(movie.tmdb_score, 7.8)
        self.assertEqual(movie.poster_path, "https://image.tmdb.org/t/p/w500/d5vxZgWJJcpLfPtHnOJmsPfUCBq.jpg")
        self.assertEqual(movie.imdb_url, "https://www.imdb.com/title/tt11604119")

        group_movie = GroupMovie.objects.get(group=self.group, movie=movie)
        self.assertEqual(group_movie.suggested_by, self.user)
        self.assertEqual(group_movie.status, GroupMovie.Status.SUGGESTED)

    @patch("movies.views.TMDBClient.get_details")
    def test_add_movie_twice_creates_one_group_movie(self, mock_get_details):
        mock_get_details.return_value = TMDB_MOVIE_DETAILS

        payload = {"movie_id": "438631", "media_type": "movie", "group_uuid": str(self.group.uuid)}
        self.client.post(reverse("add_movie"), payload)
        self.client.post(reverse("add_movie"), payload)

        self.assertEqual(Movie.objects.count(), 1)
        self.assertEqual(GroupMovie.objects.filter(group=self.group).count(), 1)

    @patch("movies.views.TMDBClient.get_details")
    def test_add_movie_api_failure(self, mock_get_details):
        mock_get_details.return_value = None
        response = self.client.post(
            reverse("add_movie"),
            {"movie_id": "438631", "media_type": "movie", "group_uuid": str(self.group.uuid)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Failed to fetch movie details from TMDB.", status_code=400)

    def test_add_movie_missing_parameters(self):
        response = self.client.post(reverse("add_movie"), {})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Missing parameters", status_code=400)

    def test_add_movie_invalid_media_type(self):
        response = self.client.post(
            reverse("add_movie"),
            {"movie_id": "438631", "media_type": "podcast", "group_uuid": str(self.group.uuid)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Invalid media type", status_code=400)

    def test_search_movies_no_query(self):
        response = self.client.post(reverse("search_movies"), {})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"error": "No query parameter provided."})
