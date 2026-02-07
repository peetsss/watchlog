from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from src.groups.models import Group, GroupMovie

from ..models import Movie

User = get_user_model()


class MovieViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.group = Group.objects.create(name="Test Group")
        self.client.login(username="testuser", password="password")

    @patch("src.movies.utils.imdb.IMDbClient.fetch_search_query")
    def test_search_movies(self, mock_fetch_search_query):
        mock_fetch_search_query.return_value = [{"title": "Test Movie", "year": "2021"}]
        response = self.client.post(reverse("search_movies"), {"query": "Test"})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"movies": [{"title": "Test Movie", "year": "2021"}]})

    @patch("src.movies.utils.imdb.IMDbClient.fetch_movie_details")
    @patch("src.movies.utils.utils.get_metacritic_url")
    @patch("src.movies.utils.utils.get_rotten_url")
    def test_add_movie(self, mock_get_rotten_url, mock_get_metacritic_url, mock_fetch_movie_details):
        mock_fetch_movie_details.return_value = {
            "Title": "Test Movie",
            "Released": "01 Jan 2021",
            "Type": "movie",
            "Plot": "Test Plot",
            "Genre": "Action",
            "Director": "Test Director",
            "Writer": "Test Writer",
            "Actors": "Test Actor",
            "Country": "Test Country",
            "Poster": "http://example.com/poster.jpg",
            "Awards": "Test Award",
            "imdbRating": "8.0",
            "Ratings": [
                {"Source": "Internet Movie Database", "Value": "8.0/10"},
                {"Source": "Rotten Tomatoes", "Value": "90%"},
            ],
            "Metascore": "75",
        }
        mock_get_rotten_url.return_value = "http://rottentomatoes.com"
        mock_get_metacritic_url.return_value = "http://metacritic.com"

        response = self.client.post(
            reverse("add_movie"),
            {"movie_id": "tt1234567", "group_code": self.group.code},
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"msg": "Test Movie has been added to Test Group"})

        movie = Movie.objects.get(imdb_id="tt1234567")
        self.assertEqual(movie.title, "Test Movie")
        self.assertEqual(movie.genre, "Action")
        self.assertEqual(movie.director, "Test Director")

        group_movie = GroupMovie.objects.get(group=self.group, movie=movie)
        self.assertEqual(group_movie.added_by, self.user.username)

    def test_add_movie_missing_parameters(self):
        response = self.client.post(reverse("add_movie"), {})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Missing parameters", status_code=400)

    def test_search_movies_no_query(self):
        response = self.client.post(reverse("search_movies"), {})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"error": "No query parameter provided."})
