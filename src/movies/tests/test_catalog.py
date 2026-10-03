from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from groups.models import Group, GroupMovie
from movies.catalog import (
    create_movie_from_details,
    full_url,
    join_names,
    parse_date,
    resolve_movie,
)
from movies.models import Movie

User = get_user_model()

DETAILS = {
    "id": 438631,
    "title": "Dune",
    "original_title": "Dune",
    "overview": "A noble family becomes embroiled in a war.",
    "status": "Released",
    "runtime": 155,
    "release_date": "2021-10-22",
    "adult": False,
    "genres": [{"id": 878, "name": "Science Fiction"}],
    "poster_path": "/abc.jpg",
    "backdrop_path": "/def.jpg",
    "vote_average": 7.8,
    "revenue": 1083300000,
    "budget": 165000000,
    "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
    "credits": {
        "crew": [{"name": "Denis Villeneuve", "job": "Director"}],
        "cast": [{"name": "Timothee Chalamet"}],
    },
    "keywords": {"keywords": [{"name": "desert"}]},
    "external_ids": {"imdb_id": "tt11604119"},
}


class CatalogHelperTests(TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2021-10-22"), date(2021, 10, 22))
        self.assertIsNone(parse_date("nope"))
        self.assertIsNone(parse_date(None))

    def test_join_names_and_full_url(self):
        self.assertEqual(join_names([{"name": "A"}, {"name": ""}]), "A")
        self.assertIsNone(join_names([]))
        self.assertEqual(full_url("https://x/", "/a.jpg"), "https://x//a.jpg")
        self.assertIsNone(full_url("https://x/", None))


class ResolveMovieTests(TestCase):
    def test_create_maps_details_without_group_side_effects(self):
        movie = create_movie_from_details(DETAILS, "movie")
        self.assertEqual(movie.title, "Dune")
        self.assertEqual(movie.release_date, date(2021, 10, 22))
        self.assertEqual(GroupMovie.objects.count(), 0)

    def test_resolve_returns_existing_without_network(self):
        existing = Movie.objects.create(tmdb_id=99, title="Cached")
        with patch("movies.catalog.TMDBClient") as client_cls:
            movie = resolve_movie(99, "movie")
            self.assertEqual(movie.id, existing.id)
            client_cls.assert_not_called()

    def test_resolve_fetches_on_miss_and_is_idempotent(self):
        client = MagicMock()
        client.get_details.return_value = DETAILS
        first = resolve_movie(438631, "movie", client=client)
        second = resolve_movie(438631, "movie", client=client)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Movie.objects.filter(tmdb_id=438631).count(), 1)
        self.assertEqual(GroupMovie.objects.count(), 0)

    def test_resolve_returns_none_on_tmdb_failure(self):
        client = MagicMock()
        client.get_details.return_value = None
        self.assertIsNone(resolve_movie(123, "movie", client=client))

    def test_invalid_media_type_raises(self):
        with self.assertRaises(ValueError):
            resolve_movie(1, "podcast", client=MagicMock())


class GroupAddMovieStillWorksTests(TestCase):
    def test_add_movie_view_uses_catalog(self):
        from django.test import Client
        from django.urls import reverse

        user = User.objects.create_user(username="u1", password="pw")
        group = Group.objects.create(name="g")
        group.members.add(user)
        client = Client()
        client.login(username="u1", password="pw")
        with patch("movies.views.resolve_movie") as mock_resolve:
            movie = Movie.objects.create(tmdb_id=7, title="Cached")
            mock_resolve.return_value = movie
            response = client.post(
                reverse("add_movie"),
                {"movie_id": "7", "media_type": "movie", "group_uuid": str(group.uuid)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(GroupMovie.objects.filter(group=group, movie=movie).exists())
