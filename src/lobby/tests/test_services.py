from unittest import main
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase as DjangoTestCase

from groups.models import Group, GroupMovie
from lobby import engine, rules, services
from lobby.exceptions import (
    AlreadyActiveLobbyError,
    InvalidChoiceError,
    InvalidPoolError,
    InvalidStateError,
    LobbyNotFoundError,
    NotAMemberError,
    NotHostError,
    NotJoinableError,
)
from lobby.models import Lobby, LobbyMembership
from movies.models import Movie
from user.models import User


def advance_one(lobby: Lobby, users) -> Lobby:
    current = lobby.pool[lobby.pool_index]
    for user in users:
        lobby = services.vote(lobby.uuid, user, current, engine.INTERESTED)
    return lobby


def play_to_final(lobby: Lobby, users) -> Lobby:
    while lobby.status == Lobby.Status.PLAYING:
        lobby = advance_one(lobby, users)
    return lobby


def pick_winner(lobby: Lobby, users) -> Lobby:
    winner = lobby.finalists[0]
    for user in users:
        lobby = services.pick(lobby.uuid, user, winner)
    return lobby


class ServiceTestCase(DjangoTestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")
        self.carol = User.objects.create_user("carol")
        self.dave = User.objects.create_user("dave")
        self.movies = [Movie.objects.create(title=f"Movie {i}") for i in range(1, 16)]
        self.group = Group.objects.create(name="Test Group")
        self.group.members.add(self.alice, self.bob, self.carol)

    def create_open(self, host, members):
        return services.create_lobby(host, members)

    def create_group(self, host, members):
        return services.create_lobby(host, members, group=self.group)

    def start(self, lobby, *users):
        for user in users:
            lobby = services.mark_ready(lobby.uuid, user)
        return lobby


class CreateLobbyTest(ServiceTestCase):
    def test_open_lobby_type_and_initial_state(self):
        lobby = self.create_open(self.alice, [self.bob, self.carol])
        self.assertEqual(lobby.type, Lobby.Type.OPEN)
        self.assertEqual(lobby.status, Lobby.Status.READY)
        self.assertEqual(lobby.host_id, self.alice.id)
        self.assertIsNone(lobby.group_id)
        self.assertEqual(lobby.pool_index, 0)
        self.assertEqual(len(lobby.pool), 15)
        self.assertEqual(lobby.version, 0)
        self.assertIsNone(lobby.started_at)

    def test_open_lobby_host_and_member_roles(self):
        lobby = self.create_open(self.alice, [self.bob, self.carol])
        self.assertEqual(lobby.memberships.count(), 3)
        self.assertEqual(lobby.memberships.filter(user=self.alice).get().role, LobbyMembership.Roles.HOST)
        self.assertEqual(lobby.memberships.filter(user=self.bob).get().role, LobbyMembership.Roles.MEMBER)

    def test_group_lobby_type_and_group_link(self):
        lobby = self.create_group(self.alice, [self.bob])
        self.assertEqual(lobby.type, Lobby.Type.GROUP)
        self.assertEqual(lobby.group_id, self.group.id)
        self.assertEqual(lobby.memberships.filter(lobby=lobby).count(), 3)

    def test_group_lobby_pulls_in_all_group_members(self):
        lobby = self.create_group(self.alice, [])
        self.assertEqual({m.user_id for m in lobby.memberships.all()}, {self.alice.id, self.bob.id, self.carol.id})

    def test_group_lobby_ignores_outsiders(self):
        mallory = User.objects.create_user("mallory")
        lobby = self.create_group(self.alice, [mallory])
        self.assertNotIn(mallory.id, {m.user_id for m in lobby.memberships.all()})

    def test_open_lobby_deduplicates_members(self):
        lobby = self.create_open(self.alice, [self.alice, self.bob, self.bob])
        self.assertEqual(lobby.memberships.count(), 2)
        self.assertEqual(lobby.memberships.filter(user=self.alice).get().role, LobbyMembership.Roles.HOST)

    def test_group_host_must_be_a_group_member(self):
        mallory = User.objects.create_user("mallory")
        with self.assertRaises(NotAMemberError):
            services.create_lobby(mallory, [], group=self.group)

    def test_group_can_only_have_one_active_lobby(self):
        self.create_group(self.alice, [])
        with self.assertRaises(AlreadyActiveLobbyError):
            self.create_group(self.bob, [])

    def test_finished_group_lobby_allows_a_new_one(self):
        first = self.create_group(self.alice, [])
        services.end_lobby(first.uuid, self.alice)
        second = self.create_group(self.alice, [])
        self.assertNotEqual(first.pk, second.pk)

    def test_explicit_pool_is_used_in_order(self):
        movie_ids = [self.movies[2].id, self.movies[0].id]
        lobby = services.create_lobby(self.alice, [], pool=movie_ids)
        self.assertEqual(lobby.pool, movie_ids)

    def test_empty_pool_is_allowed(self):
        lobby = services.create_lobby(self.alice, [], pool=[])
        self.assertEqual(lobby.pool, [])

    def test_invalid_pool_is_rejected(self):
        with self.assertRaises(InvalidPoolError):
            services.create_lobby(self.alice, [], pool=[self.movies[0].id, 999_999])
        with self.assertRaises(InvalidPoolError):
            services.create_lobby(self.alice, [], pool=[-1])
        with self.assertRaises(InvalidPoolError):
            services.create_lobby(self.alice, [], pool=[True])
        with self.assertRaises(InvalidPoolError):
            services.create_lobby(self.alice, [], pool_size=0)

    def test_random_pool_excludes_group_movies_and_adult_titles(self):
        GroupMovie.objects.create(group=self.group, movie=self.movies[0])
        adult = Movie.objects.create(title="Adult", adult=True)
        lobby = self.create_group(self.alice, [])
        self.assertNotIn(self.movies[0].id, lobby.pool)
        self.assertNotIn(adult.id, lobby.pool)
        self.assertEqual(len(lobby.pool), 14)


class JoinLobbyTest(ServiceTestCase):
    def test_join_open_ready_adds_member(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = services.join_lobby(lobby.uuid, self.carol)
        self.assertIn(self.carol.id, {m.user_id for m in lobby.memberships.all()})
        self.assertEqual(lobby.memberships.filter(user=self.carol).get().role, LobbyMembership.Roles.MEMBER)

    def test_join_bumps_version_once(self):
        lobby = self.create_open(self.alice, [self.bob])
        version = lobby.version
        lobby = services.join_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.version, version + 1)
        lobby = services.join_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.version, version + 1)

    def test_join_is_idempotent(self):
        lobby = self.create_open(self.alice, [self.bob])
        self.dave2 = services.join_lobby(lobby.uuid, self.dave)
        self.assertEqual(lobby.memberships.filter(user=self.dave).count(), 1)
        self.dave3 = services.join_lobby(lobby.uuid, self.dave)
        self.assertEqual(lobby.memberships.filter(user=self.dave).count(), 1)

    def test_join_rejects_group_lobbies(self):
        lobby = self.create_group(self.alice, [self.bob])
        with self.assertRaises(NotJoinableError):
            services.join_lobby(lobby.uuid, self.carol)

    def test_join_rejects_non_ready(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        with self.assertRaises(NotJoinableError):
            services.join_lobby(lobby.uuid, self.carol)

    def test_join_rejects_nonexistent_lobby(self):
        with self.assertRaises(LobbyNotFoundError):
            services.join_lobby(uuid4(), self.alice)


class AuthGateTest(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.lobby = self.create_open(self.alice, [self.bob, self.carol])
        self.lobby = self.start(self.lobby, self.alice, self.bob, self.carol)

    def test_non_member_cannot_vote(self):
        with self.assertRaises(NotAMemberError):
            services.vote(self.lobby.uuid, self.dave, self.lobby.pool[0], engine.INTERESTED)

    def test_non_member_cannot_mark_ready(self):
        with self.assertRaises(NotAMemberError):
            services.mark_ready(self.lobby.uuid, self.dave)

    def test_non_member_cannot_pick(self):
        with self.assertRaises(NotAMemberError):
            services.pick(self.lobby.uuid, self.dave, self.lobby.pool[0])

    def test_non_host_cannot_advance(self):
        with self.assertRaises(NotHostError):
            services.advance(self.lobby.uuid, self.bob)

    def test_non_host_cannot_finalize_or_end(self):
        with self.assertRaises(NotHostError):
            services.finalize_lobby(self.lobby.uuid, self.bob)
        with self.assertRaises(NotHostError):
            services.end_lobby(self.lobby.uuid, self.bob)


class StateValidationTest(ServiceTestCase):
    def test_mark_ready_after_start_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        with self.assertRaises(InvalidStateError):
            services.mark_ready(lobby.uuid, self.alice)

    def test_vote_before_start_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        with self.assertRaises(InvalidStateError):
            services.vote(lobby.uuid, self.alice, lobby.pool[0], engine.INTERESTED)

    def test_vote_in_final_round_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        lobby = play_to_final(lobby, [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.vote(lobby.uuid, self.alice, lobby.finalists[0], engine.INTERESTED)

    def test_pick_before_final_round_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        with self.assertRaises(InvalidStateError):
            services.pick(lobby.uuid, self.alice, lobby.pool[0])

    def test_advance_before_start_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        with self.assertRaises(InvalidStateError):
            services.advance(lobby.uuid, self.alice)

    def test_finalize_before_final_round_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        with self.assertRaises(InvalidStateError):
            services.finalize_lobby(lobby.uuid, self.alice)

    def test_invalid_vote_choice_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        with self.assertRaises(InvalidChoiceError):
            services.vote(lobby.uuid, self.alice, lobby.pool[0], "maybe")

    def test_pick_outside_finalists_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        lobby = play_to_final(lobby, [self.alice, self.bob])
        with self.assertRaises(InvalidChoiceError):
            services.pick(lobby.uuid, self.alice, 999_999)


class VersionTest(ServiceTestCase):
    def test_mark_ready_bumps_once(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 1)
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 1)

    def test_vote_bumps_only_on_change(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        version = lobby.version
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        self.assertEqual(lobby.version, version + 1)
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        self.assertEqual(lobby.version, version + 1)
        lobby = services.vote(lobby.uuid, self.alice, current, engine.WATCHED)
        self.assertEqual(lobby.version, version + 2)

    def test_pick_bumps_only_on_change(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        lobby = play_to_final(lobby, [self.alice, self.bob])
        version = lobby.version
        lobby = services.pick(lobby.uuid, self.alice, lobby.finalists[0])
        self.assertEqual(lobby.version, version + 1)
        lobby = services.pick(lobby.uuid, self.alice, lobby.finalists[0])
        self.assertEqual(lobby.version, version + 1)
        lobby = services.pick(lobby.uuid, self.alice, lobby.finalists[1])
        self.assertEqual(lobby.version, version + 2)

    def test_end_and_finalize_bump_once(self):
        lobby = self.create_open(self.alice, [self.bob])
        version = lobby.version
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, version + 1)
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, version + 1)

        final = self.create_open(self.alice, [self.bob])
        final = self.start(final, self.alice, self.bob)
        final = play_to_final(final, [self.alice, self.bob])
        version = final.version
        final = services.finalize_lobby(final.uuid, self.alice)
        self.assertEqual(final.version, version + 1)


class HappyPathTest(ServiceTestCase):
    def test_full_flow_to_winner(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertIsNotNone(lobby.started_at)
        lobby = play_to_final(lobby, users)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertEqual(len(lobby.finalists), engine.FINALIST_COUNT)
        lobby = pick_winner(lobby, users)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNotNone(lobby.winner_movie_id)
        self.assertEqual(lobby.winner_movie_id, lobby.finalists[0])
        self.assertIsNotNone(lobby.finished_at)


class StaleVoteTest(ServiceTestCase):
    def test_stale_vote_is_noop(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        first = lobby.pool[0]
        lobby = advance_one(lobby, users)
        self.assertIn(first, lobby.finalists)
        expected = {
            str(self.alice.pk): engine.INTERESTED,
            str(self.bob.pk): engine.INTERESTED,
            str(self.carol.pk): engine.INTERESTED,
        }
        self.assertEqual(lobby.votes[str(first)], expected)
        version = lobby.version
        lobby = services.vote(lobby.uuid, self.alice, first, engine.WATCHED)
        self.assertEqual(lobby.votes[str(first)], expected)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertEqual(lobby.pool_index, 1)
        self.assertEqual(lobby.version, version)

    def test_vote_for_movie_outside_pool_is_noop(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        version = lobby.version
        lobby = services.vote(lobby.uuid, self.alice, 999_999, engine.INTERESTED)
        self.assertEqual(lobby.version, version)


class LeaveTest(ServiceTestCase):
    def test_leave_removes_membership_and_ready(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        version = lobby.version
        lobby = services.leave_lobby(lobby.uuid, self.bob)
        self.assertEqual(lobby.memberships.count(), 2)
        self.assertNotIn(str(self.bob.pk), lobby.ready)
        self.assertIn(str(self.alice.pk), lobby.ready)
        self.assertEqual(lobby.version, version + 1)

    def test_leave_prunes_votes_so_remaining_members_can_advance(self):
        lobby = self.create_open(self.alice, [self.bob, self.carol])
        lobby = self.start(lobby, self.alice, self.bob, self.carol)
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        lobby = services.leave_lobby(lobby.uuid, self.bob)
        self.assertNotIn(str(self.bob.pk), lobby.votes.get(str(current), {}))
        lobby = services.vote(lobby.uuid, self.carol, current, engine.INTERESTED)
        self.assertIn(current, lobby.finalists)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)

    def test_leave_completes_the_current_round_immediately(self):
        lobby = self.create_open(self.alice, [self.bob, self.carol])
        lobby = self.start(lobby, self.alice, self.bob, self.carol)
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertIn(current, lobby.finalists)
        self.assertEqual(lobby.pool_index, 1)

    def test_leave_can_start_the_game(self):
        lobby = self.create_open(self.alice, [self.bob, self.carol])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        lobby = services.mark_ready(lobby.uuid, self.bob)
        self.assertEqual(lobby.status, Lobby.Status.READY)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertIsNotNone(lobby.started_at)

    def test_leave_in_final_round_can_resolve_the_winner(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        winner = lobby.finalists[0]
        lobby = services.pick(lobby.uuid, self.alice, winner)
        lobby = services.pick(lobby.uuid, self.bob, winner)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertEqual(lobby.winner_movie_id, winner)

    def test_leave_finished_lobby_is_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        services.end_lobby(lobby.uuid, self.alice)
        with self.assertRaises(InvalidStateError):
            services.leave_lobby(lobby.uuid, self.bob)

    def test_leave_host_rejected(self):
        lobby = self.create_open(self.alice, [self.bob, self.carol])
        with self.assertRaises(NotAMemberError):
            services.leave_lobby(lobby.uuid, self.alice)

    def test_leave_non_member_rejected(self):
        lobby = self.create_open(self.alice, [self.bob])
        with self.assertRaises(NotAMemberError):
            services.leave_lobby(lobby.uuid, self.dave)


class AdvanceTest(ServiceTestCase):
    def test_force_advance_skips_current_not_added_to_finalists(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        current = lobby.pool[lobby.pool_index]
        lobby = services.advance(lobby.uuid, self.alice)
        self.assertEqual(lobby.pool_index, 1)
        self.assertNotIn(current, lobby.finalists)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)


class ExhaustionTest(ServiceTestCase):
    def test_exhaustion_with_finalists_goes_to_final_round(self):
        one = self.dave
        lobby = services.create_lobby(one, [], pool_size=2)
        lobby = services.mark_ready(lobby.uuid, one)
        lobby = services.vote(lobby.uuid, one, lobby.pool[0], engine.INTERESTED)
        lobby = services.vote(lobby.uuid, one, lobby.pool[1], engine.WATCHED)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertEqual(len(lobby.finalists), 1)

    def test_exhaustion_without_finalists_ends_no_winner(self):
        one = self.dave
        lobby = services.create_lobby(one, [], pool_size=2)
        lobby = services.mark_ready(lobby.uuid, one)
        lobby = services.vote(lobby.uuid, one, lobby.pool[0], engine.WATCHED)
        lobby = services.vote(lobby.uuid, one, lobby.pool[1], engine.WATCHED)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertEqual(len(lobby.finalists), 0)
        self.assertIsNotNone(lobby.finished_at)

    def test_empty_pool_finishes_when_everyone_is_ready(self):
        lobby = services.create_lobby(self.alice, [], pool=[])
        version = lobby.version
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertIsNone(lobby.started_at)
        self.assertIsNotNone(lobby.finished_at)
        self.assertEqual(lobby.version, version + 1)


class FinalizeTest(ServiceTestCase):
    def test_finalize_without_picks_ends_without_winner(self):
        users = [self.alice, self.bob]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        lobby = services.finalize_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertIsNotNone(lobby.finished_at)

    def test_finalize_with_partial_picks_resolves_winner(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        winner = lobby.finalists[0]
        lobby = services.pick(lobby.uuid, self.alice, winner)
        lobby = services.pick(lobby.uuid, self.bob, winner)
        lobby = services.finalize_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertEqual(lobby.winner_movie_id, winner)


class EndTest(ServiceTestCase):
    def test_end_from_ready(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertIsNone(lobby.started_at)
        self.assertIsNotNone(lobby.finished_at)

    def test_end_from_playing(self):
        lobby = self.create_open(self.alice, [self.bob])
        lobby = self.start(lobby, self.alice, self.bob)
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertIsNotNone(lobby.started_at)

    def test_end_from_final_round_has_no_winner(self):
        users = [self.alice, self.bob]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)


class GroupWinnerTest(ServiceTestCase):
    def test_group_winner_is_added_to_group_movies(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_group(self.alice, [])
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        winner = lobby.finalists[0]
        lobby = pick_winner(lobby, users)
        self.assertEqual(lobby.winner_movie_id, winner)
        group_movie = GroupMovie.objects.get(group=self.group, movie_id=winner)
        self.assertEqual(group_movie.status, GroupMovie.Status.SUGGESTED)
        self.assertEqual(group_movie.suggested_by_id, self.alice.id)

    def test_existing_group_movie_is_not_overwritten(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_group(self.alice, [])
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        winner = lobby.finalists[0]
        existing = GroupMovie.objects.create(group=self.group, movie_id=winner, suggested_by=self.bob)
        pick_winner(lobby, users)
        existing.refresh_from_db()
        self.assertEqual(existing.suggested_by_id, self.bob.id)
        self.assertEqual(GroupMovie.objects.filter(group=self.group, movie_id=winner).count(), 1)

    def test_open_lobby_winner_is_not_added_to_group_movies(self):
        users = [self.alice, self.bob]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        pick_winner(lobby, users)
        self.assertEqual(GroupMovie.objects.count(), 0)

    def test_group_lobby_without_winner_adds_nothing(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_group(self.alice, [])
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        services.finalize_lobby(lobby.uuid, self.alice)
        self.assertEqual(GroupMovie.objects.count(), 0)


class ReadModelTest(ServiceTestCase):
    def test_state_hides_other_players_votes(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        current = lobby.pool[lobby.pool_index]
        services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        services.vote(lobby.uuid, self.bob, current, engine.WATCHED)

        alice_state = services.get_state(lobby.uuid, self.alice)
        bob_state = services.get_state(lobby.uuid, self.bob)
        self.assertEqual(alice_state.viewer_vote, engine.INTERESTED)
        self.assertEqual(bob_state.viewer_vote, engine.WATCHED)
        self.assertEqual(alice_state.submitted_count, 2)
        self.assertEqual(alice_state.player_count, 3)
        self.assertEqual(alice_state.current_movie.id, current)
        self.assertTrue(alice_state.viewer_is_host)
        self.assertFalse(bob_state.viewer_is_host)

    def test_state_lists_players_with_ready_flags(self):
        lobby = self.create_open(self.alice, [self.bob])
        services.mark_ready(lobby.uuid, self.alice)
        state = services.get_state(lobby.uuid, self.alice)
        self.assertEqual(state.players[0].user_id, self.alice.id)
        self.assertTrue(state.players[0].is_host)
        self.assertTrue(state.players[0].is_ready)
        self.assertFalse(state.players[1].is_ready)
        self.assertEqual(state.status, Lobby.Status.READY)
        self.assertEqual(state.submitted_count, 0)
        self.assertIsNone(state.viewer_vote)

    def test_state_hides_other_players_picks(self):
        users = [self.alice, self.bob]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        winner = lobby.finalists[0]
        services.pick(lobby.uuid, self.alice, winner)

        alice_state = services.get_state(lobby.uuid, self.alice)
        bob_state = services.get_state(lobby.uuid, self.bob)
        self.assertEqual(alice_state.viewer_pick, winner)
        self.assertIsNone(bob_state.viewer_pick)
        self.assertTrue(alice_state.finalists[0].viewer_picked)
        self.assertFalse(bob_state.finalists[0].viewer_picked)
        self.assertEqual(bob_state.finalists[0].pick_count, 1)
        self.assertEqual(bob_state.submitted_count, 1)

    def test_state_exposes_winner_and_group(self):
        users = [self.alice, self.bob, self.carol]
        lobby = self.create_group(self.alice, [])
        lobby = self.start(lobby, *users)
        lobby = play_to_final(lobby, users)
        winner = lobby.finalists[0]
        lobby = pick_winner(lobby, users)
        state = services.get_state(lobby.uuid, self.alice)
        self.assertEqual(state.group_uuid, self.group.uuid)
        self.assertEqual(state.group_name, self.group.name)
        self.assertEqual(state.winner.id, winner)
        self.assertEqual(state.status, Lobby.Status.FINISHED)
        self.assertIsNotNone(state.started_at)
        self.assertIsNotNone(state.finished_at)

    def test_state_uses_a_constant_number_of_queries(self):
        users = [self.alice, self.bob]
        lobby = self.create_open(self.alice, users)
        lobby = self.start(lobby, *users)
        with self.assertNumQueries(3):
            services.get_state(lobby.uuid, self.alice)

    def test_non_member_cannot_read_state(self):
        lobby = self.create_open(self.alice, [self.bob])
        with self.assertRaises(NotAMemberError):
            services.get_state(lobby.uuid, self.dave)
        with self.assertRaises(NotAMemberError):
            services.get_lobby_for_member(lobby.uuid, self.dave)

    def test_get_lobby_for_member_returns_lobby(self):
        lobby = self.create_open(self.alice, [self.bob])
        self.assertEqual(services.get_lobby_for_member(lobby.uuid, self.bob).pk, lobby.pk)

    def test_get_active_group_lobby(self):
        lobby = self.create_group(self.alice, [])
        self.assertEqual(services.get_active_group_lobby(self.group).pk, lobby.pk)
        services.end_lobby(lobby.uuid, self.alice)
        self.assertIsNone(services.get_active_group_lobby(self.group))


class ConstraintTest(ServiceTestCase):
    def test_unique_active_lobby_per_group(self):
        self.create_group(self.alice, [])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lobby.objects.create(type=Lobby.Type.GROUP, group=self.group, host=self.bob)

    def test_group_lobby_requires_a_group(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lobby.objects.create(type=Lobby.Type.GROUP, group=None, host=self.alice)

    def test_open_lobby_rejects_a_group(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lobby.objects.create(type=Lobby.Type.OPEN, group=self.group, host=self.alice)

    def test_one_host_membership_per_lobby(self):
        lobby = Lobby.objects.create(type=Lobby.Type.OPEN, host=self.alice)
        LobbyMembership.objects.create(lobby=lobby, user=self.alice, role=LobbyMembership.Roles.HOST)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyMembership.objects.create(lobby=lobby, user=self.bob, role=LobbyMembership.Roles.HOST)


class ErrorContractTest(ServiceTestCase):
    def test_unknown_lobby_raises_not_found(self):
        with self.assertRaises(LobbyNotFoundError):
            services.mark_ready(uuid4(), self.alice)

    def test_pool_choice_constants_are_canonical(self):
        self.assertEqual(rules.ACTIVE_STATUSES, frozenset({rules.READY, rules.PLAYING, rules.FINAL_ROUND}))
        self.assertIn(rules.INTERESTED, rules.VOTE_CHOICES)


if __name__ == "__main__":
    main()
