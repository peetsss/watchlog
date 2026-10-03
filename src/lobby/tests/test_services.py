from django.contrib.auth import get_user_model
from django.test import TestCase

from groups.models import Group, GroupMovie
from lobby import rules, services
from lobby.models import (
    LobbyBallot,
    LobbyCard,
    LobbyParticipant,
    LobbySession,
    WatchlistOfferResponse,
)
from movies.models import Movie, UserMovieLibrary

User = get_user_model()


def make_users(n=3):
    return [User.objects.create_user(username=f"u{i}", password="pw") for i in range(n)]


def make_group(users, name="g"):
    group = Group.objects.create(name=name)
    group.members.add(*users)
    return group


def make_movie(tmdb_id, title):
    return Movie.objects.create(tmdb_id=tmdb_id, title=title)


class SessionLifecycleTests(TestCase):
    def test_create_join_start_freezes_roster(self):
        users = make_users(2)
        group = make_group(users)
        session = services.create_session(group, users[0])
        self.assertEqual(session.status, LobbySession.Status.WAITING)
        self.assertEqual(len(session.quiz_snapshot["questions"]), 3)

        services.join_session(session, users[1])
        self.assertEqual(session.participants.count(), 2)

        started = services.start_session(session, users[0])
        self.assertEqual(started.status, LobbySession.Status.ACTIVE)
        states = set(started.participants.values_list("state", flat=True))
        self.assertEqual(states, {LobbyParticipant.State.ACTIVE})

        # Roster frozen: late join rejected.
        late = User.objects.create_user(username="late", password="pw")
        group.members.add(late)
        with self.assertRaises(services.LobbyError):
            services.join_session(started, late)

    def test_only_members_may_join_and_only_host_starts(self):
        users = make_users(2)
        outsider = User.objects.create_user(username="out", password="pw")
        group = make_group(users)
        session = services.create_session(group, users[0])
        with self.assertRaises(services.LobbyError):
            services.join_session(session, outsider)
        with self.assertRaises(services.LobbyError):
            services.start_session(session, users[1])

    def test_min_participants_enforced(self):
        (solo,) = make_users(1)
        group = make_group([solo])
        session = services.create_session(group, solo)
        with self.assertRaises(services.LobbyError):
            services.start_session(session, solo)

    def test_duplicate_session_rejected_and_host_can_end(self):
        users = make_users(2)
        group = make_group(users)
        session = services.create_session(group, users[0])
        with self.assertRaises(services.LobbyError):
            services.create_session(group, users[1])
        ended = services.end_session(session, users[0])
        self.assertEqual(ended.status, LobbySession.Status.CANCELLED)


class BallotFlowTests(TestCase):
    def setUp(self):
        self.users = make_users(2)
        self.group = make_group(self.users)
        self.movies = [make_movie(1, "Dune"), make_movie(2, "Arrival"), make_movie(3, "Interstellar")]
        self.session = services.create_session(self.group, self.users[0])
        services.join_session(self.session, self.users[1])
        services.queue_movies(self.session, self.movies)
        self.session = services.start_session(self.session, self.users[0])

    def current(self):
        return LobbyCard.objects.get(session=self.session, status=LobbyCard.Status.CURRENT)

    def test_all_want_matches_and_adds_group_movie(self):
        card = self.current()
        r1 = services.submit_ballot(self.session, self.users[0], "want")
        self.assertEqual(r1.outcome, "pending")
        # Want persists to personal watchlist even before resolution.
        self.assertTrue(
            UserMovieLibrary.objects.filter(
                user=self.users[0], movie=card.movie, watchlist_added_at__isnull=False
            ).exists()
        )
        r2 = services.submit_ballot(self.session, self.users[1], "want")
        self.assertEqual(r2.outcome, "matched")
        card.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(card.status, LobbyCard.Status.MATCHED)
        self.assertEqual(self.session.status, LobbySession.Status.MATCHED)
        gm = GroupMovie.objects.get(group=self.group, movie=card.movie)
        self.assertEqual(gm.status, GroupMovie.Status.SUGGESTED)
        # Both watchlists retained after match.
        self.assertEqual(UserMovieLibrary.objects.filter(movie=card.movie, watchlist_added_at__isnull=False).count(), 2)

    def test_veto_advances_and_keeps_want_watchlist(self):
        first = self.current()
        services.submit_ballot(self.session, self.users[0], "want")
        result = services.submit_ballot(self.session, self.users[1], "not_interested")
        self.assertEqual(result.outcome, "vetoed")
        first.refresh_from_db()
        self.assertEqual(first.status, LobbyCard.Status.VETOED)
        # Vetoed card's Want still left a personal watchlist entry.
        self.assertTrue(
            UserMovieLibrary.objects.filter(
                user=self.users[0], movie=first.movie, watchlist_added_at__isnull=False
            ).exists()
        )
        # Next card is now current.
        nxt = LobbyCard.objects.get(session=self.session, status=LobbyCard.Status.CURRENT)
        self.assertNotEqual(nxt.id, first.id)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, LobbySession.Status.ACTIVE)

    def test_watched_records_history_and_creates_offer(self):
        card = self.current()
        services.submit_ballot(self.session, self.users[0], "watched")
        # History written immediately, watchlist cleared.
        entry = UserMovieLibrary.objects.get(user=self.users[0], movie=card.movie)
        self.assertIsNotNone(entry.first_watched_at)
        self.assertIsNone(entry.watchlist_added_at)

        result = services.submit_ballot(self.session, self.users[1], "want")
        self.assertEqual(result.outcome, "watched")
        card.refresh_from_db()
        self.assertEqual(card.status, LobbyCard.Status.WATCHED)
        # Personal watch never marks group copy Watched.
        self.assertFalse(GroupMovie.objects.filter(group=self.group, movie=card.movie).exists())
        responses = WatchlistOfferResponse.objects.filter(offer__card=card)
        self.assertEqual(responses.count(), 1)
        self.assertEqual(responses.first().participant.user, self.users[1])

    def test_mixed_watched_and_veto_still_offers(self):
        card = self.current()
        services.submit_ballot(self.session, self.users[0], "watched")
        result = services.submit_ballot(self.session, self.users[1], "not_interested")
        self.assertEqual(result.outcome, "watched")
        self.assertTrue(WatchlistOfferResponse.objects.filter(offer__card=card).exists())

    def test_duplicate_ballot_is_idempotent(self):
        card = self.current()
        services.submit_ballot(self.session, self.users[0], "want")
        before = UserMovieLibrary.objects.get(user=self.users[0], movie=card.movie).watchlist_added_at
        retry = services.submit_ballot(self.session, self.users[0], "want")
        self.assertEqual(retry.outcome, "pending")
        self.assertEqual(LobbyBallot.objects.filter(card=card, participant__user=self.users[0]).count(), 1)
        after = UserMovieLibrary.objects.get(user=self.users[0], movie=card.movie).watchlist_added_at
        self.assertEqual(before, after)

    def test_non_participant_and_stale_card_rejected(self):
        outsider = User.objects.create_user(username="out", password="pw")
        self.group.members.add(outsider)
        with self.assertRaises(services.LobbyError):
            services.submit_ballot(self.session, outsider, "want")
        with self.assertRaises(services.LobbyError):
            services.submit_ballot(self.session, self.users[0], "bogus")
        queued = LobbyCard.objects.filter(session=self.session, status=LobbyCard.Status.QUEUED).first()
        with self.assertRaises(services.LobbyError):
            services.submit_ballot(self.session, self.users[0], "want", card_id=queued.id)

    def test_ballots_hidden_until_complete(self):
        state = services.get_session_state(self.session, self.users[0])
        self.assertEqual(state["submitted_count"], 0)
        self.assertIsNone(state["own_choice"])
        services.submit_ballot(self.session, self.users[0], "want")
        other_state = services.get_session_state(self.session, self.users[1])
        self.assertEqual(other_state["submitted_count"], 1)
        self.assertIsNone(other_state["own_choice"])
        self.assertNotIn("choices", other_state)


class OfferResponseTests(TestCase):
    def setUp(self):
        self.users = make_users(2)
        self.group = make_group(self.users)
        self.movie = make_movie(10, "Dune")
        self.session = services.create_session(self.group, self.users[0])
        services.join_session(self.session, self.users[1])
        services.queue_movies(self.session, [self.movie, make_movie(11, "Arrival")])
        self.session = services.start_session(self.session, self.users[0])
        card = LobbyCard.objects.get(session=self.session, status=LobbyCard.Status.CURRENT)
        services.submit_ballot(self.session, self.users[0], "watched")
        services.submit_ballot(self.session, self.users[1], "want")
        self.card = LobbyCard.objects.get(pk=card.pk)

    def test_add_creates_one_group_movie_and_closes_rest(self):
        offer = self.card.watch_offer
        resp = services.respond_to_offer(offer.id, self.users[1], "add")
        self.assertEqual(resp.status, "added")
        self.assertEqual(GroupMovie.objects.filter(group=self.group, movie=self.card.movie).count(), 1)
        # Replay is idempotent.
        again = services.respond_to_offer(offer.id, self.users[1], "add")
        self.assertEqual(again.status, "added")
        self.assertEqual(GroupMovie.objects.filter(group=self.group, movie=self.card.movie).count(), 1)

    def test_dismiss_creates_no_group_movie(self):
        offer = self.card.watch_offer
        resp = services.respond_to_offer(offer.id, self.users[1], "dismiss")
        self.assertEqual(resp.status, "dismissed")
        self.assertFalse(GroupMovie.objects.filter(group=self.group, movie=self.card.movie).exists())

    def test_only_owner_may_respond(self):
        offer = self.card.watch_offer
        with self.assertRaises(services.LobbyError):
            services.respond_to_offer(offer.id, self.users[0], "add")

    def test_reconnect_returns_pending_offers(self):
        state = services.get_session_state(self.session, self.users[1])
        self.assertEqual(len(state["pending_offers"]), 1)
        self.assertEqual(state["pending_offers"][0]["movie_id"], self.card.movie_id)


class ManualNominationTests(TestCase):
    def test_manual_queues_ahead_without_interrupting_current(self):
        users = make_users(2)
        group = make_group(users)
        sys_movies = [make_movie(i, f"Sys {i}") for i in range(1, 4)]
        manual = make_movie(99, "Manual")
        session = services.create_session(group, users[0])
        services.join_session(session, users[1])
        services.queue_movies(session, sys_movies)
        session = services.start_session(session, users[0])
        current = LobbyCard.objects.get(session=session, status=LobbyCard.Status.CURRENT)
        card = services.nominate_manual_movie(session, users[0], manual)
        self.assertEqual(card.source, LobbyCard.Source.MANUAL)
        self.assertEqual(card.picked_by, users[0])
        current.refresh_from_db()
        self.assertEqual(current.status, LobbyCard.Status.CURRENT)
        # Manual sits directly after current, before remaining system cards.
        ordered = list(LobbyCard.objects.filter(session=session, status__in=["current", "queued"]).order_by("position"))
        self.assertEqual(ordered[0].id, current.id)
        self.assertEqual(ordered[1].id, card.id)

    def test_duplicate_nomination_returns_existing_and_group_listed_rejected(self):
        users = make_users(2)
        group = make_group(users)
        movie = make_movie(50, "Pick")
        session = services.create_session(group, users[0])
        services.join_session(session, users[1])
        first = services.nominate_manual_movie(session, users[0], movie)
        second = services.nominate_manual_movie(session, users[1], movie)
        self.assertEqual(first.id, second.id)
        GroupMovie.objects.create(group=group, movie=make_movie(51, "Listed"))
        listed = Movie.objects.get(tmdb_id=51)
        with self.assertRaises(services.LobbyError):
            services.nominate_manual_movie(session, users[0], listed)


class ExhaustionTests(TestCase):
    def test_exhausted_when_queue_empty(self):
        users = make_users(2)
        group = make_group(users)
        session = services.create_session(group, users[0])
        services.join_session(session, users[1])
        services.queue_movies(session, [make_movie(1, "Only")])
        session = services.start_session(session, users[0])
        services.submit_ballot(session, users[0], "want")
        result = services.submit_ballot(session, users[1], "not_interested")
        self.assertEqual(result.outcome, "vetoed")
        session.refresh_from_db()
        self.assertEqual(session.status, LobbySession.Status.EXHAUSTED)

    def test_cap_exhaustion(self):
        users = make_users(2)
        group = make_group(users)
        session = services.create_session(group, users[0])
        services.join_session(session, users[1])
        session.resolved_count = rules.MAX_RESOLVED_CARDS - 1
        session.save(update_fields=["resolved_count"])
        services.queue_movies(session, [make_movie(1, "A"), make_movie(2, "B")])
        session = services.start_session(session, users[0])
        services.submit_ballot(session, users[0], "want")
        services.submit_ballot(session, users[1], "not_interested")
        session.refresh_from_db()
        self.assertEqual(session.status, LobbySession.Status.EXHAUSTED)
        self.assertEqual(session.resolved_count, rules.MAX_RESOLVED_CARDS)
