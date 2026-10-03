from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from movies.models import Movie, UserMovieLibrary

User = get_user_model()


class ModelStrTests(TestCase):
    def test_str_never_queries_db(self):
        user = User.objects.create_user(username="struser", password="pw")
        movie = Movie.objects.create(tmdb_id=999002, title="Str Movie")
        entry = UserMovieLibrary.objects.create(user=user, movie=movie, watchlist_added_at=timezone.now())
        with self.assertNumQueries(0):
            str(movie)
            str(entry)
