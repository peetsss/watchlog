from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from groups.models import Group, GroupMovie, Review
from movies.models import Movie, UserMovieLibrary
from movies.services import (
    add_to_personal_watchlist,
    get_personal_history,
    get_personal_watchlist,
    mark_personally_watched,
    remove_from_personal_watchlist,
)

User = get_user_model()


def make_movie(tmdb_id=1, title="Dune"):
    return Movie.objects.create(tmdb_id=tmdb_id, title=title)


class UserMovieLibraryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        self.movie = make_movie()

    def test_unique_user_movie(self):
        add_to_personal_watchlist(self.user, self.movie)
        with self.assertRaises(IntegrityError):
            UserMovieLibrary.objects.create(user=self.user, movie=self.movie, watchlist_added_at=timezone.now())

    def test_check_constraint_requires_state(self):
        with self.assertRaises(IntegrityError):
            UserMovieLibrary.objects.create(user=self.user, movie=self.movie)


class PersonalLibraryServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        self.other = User.objects.create_user(username="u2", password="pw")
        self.movie = make_movie()

    def test_add_is_idempotent_and_retains_watched(self):
        mark_personally_watched(self.user, self.movie)
        first = UserMovieLibrary.objects.get(user=self.user, movie=self.movie)
        first_watched_at = first.first_watched_at
        self.assertIsNone(first.watchlist_added_at)

        add_to_personal_watchlist(self.user, self.movie)
        add_to_personal_watchlist(self.user, self.movie)
        entry = UserMovieLibrary.objects.get(user=self.user, movie=self.movie)
        self.assertIsNotNone(entry.watchlist_added_at)
        self.assertEqual(entry.first_watched_at, first_watched_at)
        self.assertEqual(UserMovieLibrary.objects.filter(user=self.user, movie=self.movie).count(), 1)

    def test_mark_watched_clears_watchlist_but_keeps_first_timestamp(self):
        add_to_personal_watchlist(self.user, self.movie)
        first = mark_personally_watched(self.user, self.movie)
        first_ts = first.first_watched_at
        self.assertIsNone(first.watchlist_added_at)

        second = mark_personally_watched(self.user, self.movie)
        self.assertEqual(second.first_watched_at, first_ts)
        self.assertEqual(UserMovieLibrary.objects.filter(user=self.user, movie=self.movie).count(), 1)

    def test_remove_keeps_watched_history(self):
        add_to_personal_watchlist(self.user, self.movie)
        mark_personally_watched(self.user, self.movie)
        add_to_personal_watchlist(self.user, self.movie)
        remove_from_personal_watchlist(self.user, self.movie)
        entry = UserMovieLibrary.objects.get(user=self.user, movie=self.movie)
        self.assertIsNone(entry.watchlist_added_at)
        self.assertIsNotNone(entry.first_watched_at)

    def test_remove_deletes_watchlist_only_row(self):
        add_to_personal_watchlist(self.user, self.movie)
        remove_from_personal_watchlist(self.user, self.movie)
        self.assertFalse(UserMovieLibrary.objects.filter(user=self.user, movie=self.movie).exists())

    def test_remove_missing_is_noop(self):
        remove_from_personal_watchlist(self.user, self.movie)

    def test_scopes_are_owner_specific(self):
        add_to_personal_watchlist(self.user, self.movie)
        self.assertEqual(get_personal_watchlist(self.user).count(), 1)
        self.assertEqual(get_personal_watchlist(self.other).count(), 0)
        self.assertEqual(get_personal_history(self.other).count(), 0)


class PersonalLibraryViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pw")
        self.other = User.objects.create_user(username="u2", password="pw")
        self.movie = make_movie()
        self.client.login(username="u1", password="pw")

    def test_library_page_is_owner_scoped(self):
        add_to_personal_watchlist(self.other, self.movie)
        response = self.client.get(reverse("personal_library"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Dune")

        add_to_personal_watchlist(self.user, self.movie)
        response = self.client.get(reverse("personal_library"))
        self.assertContains(response, "Dune")

    def test_add_remove_watched_actions(self):
        self.client.post(reverse("personal_watchlist_add"), {"movie_id": self.movie.pk})
        self.assertTrue(
            UserMovieLibrary.objects.filter(
                user=self.user, movie=self.movie, watchlist_added_at__isnull=False
            ).exists()
        )
        self.client.post(reverse("personal_mark_watched"), {"movie_id": self.movie.pk})
        entry = UserMovieLibrary.objects.get(user=self.user, movie=self.movie)
        self.assertIsNotNone(entry.first_watched_at)
        self.assertIsNone(entry.watchlist_added_at)

        self.client.post(reverse("personal_watchlist_add"), {"movie_id": self.movie.pk})
        entry.refresh_from_db()
        self.assertIsNotNone(entry.watchlist_added_at)
        self.assertIsNotNone(entry.first_watched_at)

        self.client.post(reverse("personal_watchlist_remove"), {"movie_id": self.movie.pk})
        entry.refresh_from_db()
        self.assertIsNone(entry.watchlist_added_at)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("personal_library")).status_code, 302)


class ReviewRecordsPersonalHistoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pw")
        self.other = User.objects.create_user(username="u2", password="pw")
        self.group = Group.objects.create(name="g")
        self.group.members.add(self.user, self.other)
        self.movie = make_movie()
        self.group_movie = GroupMovie.objects.create(group=self.group, movie=self.movie)
        self.client.login(username="u1", password="pw")

    def test_review_creates_personal_history_without_group_status_side_effect(self):
        response = self.client.post(
            reverse("add_user_score"),
            {"movie_id": self.movie.tmdb_id, "group_uuid": str(self.group.uuid), "score": "8"},
        )
        self.assertEqual(response.status_code, 302)
        entry = UserMovieLibrary.objects.get(user=self.user, movie=self.movie)
        self.assertIsNotNone(entry.first_watched_at)
        self.group_movie.refresh_from_db()
        # Single review in multi-member-agnostic group must not flip status here.
        self.assertEqual(self.group_movie.status, GroupMovie.Status.SUGGESTED)

    def test_personal_actions_never_mutate_group_movie(self):
        add_to_personal_watchlist(self.user, self.movie)
        mark_personally_watched(self.user, self.movie)
        self.group_movie.refresh_from_db()
        self.assertEqual(self.group_movie.status, GroupMovie.Status.SUGGESTED)

    def test_group_match_placeholder_does_not_touch_other_users(self):
        # Documents FR-03: group writes must not touch other users' libraries.
        GroupMovie.objects.filter(pk=self.group_movie.pk).update(status=GroupMovie.Status.WATCHED)
        self.assertFalse(UserMovieLibrary.objects.filter(user=self.user).exists())
        Review.objects.create(group_movie=self.group_movie, user=self.user, score=9)
        self.assertEqual(Review.objects.count(), 1)
