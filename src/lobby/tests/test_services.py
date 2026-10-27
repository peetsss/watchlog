from collections.abc import Iterable
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


class LobbyTestCase(DjangoTestCase):
    alice: User
    bob: User
    carol: User
    dave: User
    movies: list[Movie]
    group: Group

    @classmethod
    def setUpTestData(cls) -> None:
        cls.alice = User.objects.create_user("alice")
        cls.bob = User.objects.create_user("bob")
        cls.carol = User.objects.create_user("carol")
        cls.dave = User.objects.create_user("dave")
        cls.movies = [Movie.objects.create(title=f"Movie {i}") for i in range(1, 16)]
        cls.group = Group.objects.create(name="Test Group")
        cls.group.members.add(cls.alice, cls.bob, cls.carol)

    def create_open(self, host: User | None = None, members: Iterable[User] = ()) -> Lobby:
        return services.create_lobby(host or self.alice, members)

    def create_group(self, host: User | None = None) -> Lobby:
        return services.create_lobby(host or self.alice, group=self.group)

    def members(self, lobby: Lobby) -> list[User]:
        return [membership.user for membership in lobby.memberships.select_related("user")]

    def start(self, lobby: Lobby, users: Iterable[User] | None = None) -> Lobby:
        for user in self.members(lobby) if users is None else users:
            lobby = services.mark_ready(lobby.uuid, user)
        return lobby

    def vote_current(self, lobby: Lobby, users: Iterable[User], choice: str = engine.INTERESTED) -> Lobby:
        current = lobby.pool[lobby.pool_index]
        for user in users:
            lobby = services.vote(lobby.uuid, user, current, choice)
        return lobby

    def play_to_final(self, lobby: Lobby, users: Iterable[User] | None = None) -> Lobby:
        voters = list(users) if users is not None else self.members(lobby)
        while lobby.status == Lobby.Status.PLAYING:
            lobby = self.vote_current(lobby, voters)
        return lobby

    def pick_for_all(self, lobby: Lobby, movie_id: int) -> Lobby:
        for user in self.members(lobby):
            lobby = services.pick(lobby.uuid, user, movie_id)
        return lobby


class CreateLobbyTest(LobbyTestCase):
    def test_open_lobby_initial_state_and_members(self) -> None:
        lobby = self.create_open(members=[self.alice, self.bob, self.bob])
        self.assertEqual(lobby.type, Lobby.Type.OPEN)
        self.assertEqual(lobby.status, Lobby.Status.READY)
        self.assertEqual(lobby.host_id, self.alice.id)
        self.assertIsNone(lobby.group_id)
        self.assertEqual(lobby.pool_index, 0)
        self.assertEqual(len(lobby.pool), len(self.movies))
        self.assertEqual(lobby.version, 0)
        self.assertIsNone(lobby.started_at)
        roles = dict(lobby.memberships.values_list("user_id", "role"))
        self.assertEqual(
            roles,
            {
                self.alice.id: LobbyMembership.Roles.HOST,
                self.bob.id: LobbyMembership.Roles.MEMBER,
            },
        )

    def test_group_lobby_snapshots_group_members_and_ignores_outsiders(self) -> None:
        mallory = User.objects.create_user("mallory")
        lobby = services.create_lobby(self.alice, [mallory], group=self.group)
        self.assertEqual(lobby.type, Lobby.Type.GROUP)
        self.assertEqual(lobby.group_id, self.group.id)
        self.assertEqual(
            {membership.user_id for membership in lobby.memberships.all()}, {self.alice.id, self.bob.id, self.carol.id}
        )
        self.assertNotIn(mallory.id, {membership.user_id for membership in lobby.memberships.all()})

    def test_group_host_must_be_a_group_member(self) -> None:
        mallory = User.objects.create_user("mallory")
        with self.assertRaises(NotAMemberError):
            services.create_lobby(mallory, [], group=self.group)

    def test_group_can_have_one_active_lobby_and_reuse_it_after_end(self) -> None:
        first = self.create_group()
        with self.assertRaises(AlreadyActiveLobbyError):
            self.create_group(self.bob)
        services.end_lobby(first.uuid, self.alice)
        second = self.create_group()
        self.assertNotEqual(first.pk, second.pk)

    def test_explicit_pool_preserves_order_and_deduplicates(self) -> None:
        movie_ids = [self.movies[2].id, self.movies[0].id, self.movies[2].id]
        lobby = services.create_lobby(self.alice, [], pool=movie_ids)
        self.assertEqual(lobby.pool, movie_ids[:2])

    def test_empty_pool_is_allowed(self) -> None:
        lobby = services.create_lobby(self.alice, [], pool=[])
        self.assertEqual(lobby.pool, [])

    def test_invalid_pool_and_size_are_rejected(self) -> None:
        cases = (
            ([self.movies[0].id, 999_999], rules.POOL_SIZE),
            ([-1], rules.POOL_SIZE),
            ([True], rules.POOL_SIZE),
            (None, 0),
        )
        for pool, size in cases:
            with self.subTest(pool=pool, size=size), self.assertRaises(InvalidPoolError):
                services.create_lobby(self.alice, [], pool=pool, pool_size=size)

    def test_random_pool_excludes_group_movies_and_adult_titles(self) -> None:
        GroupMovie.objects.create(group=self.group, movie=self.movies[0])
        adult = Movie.objects.create(title="Adult", adult=True)
        lobby = self.create_group()
        self.assertEqual(set(lobby.pool), {movie.id for movie in self.movies[1:]})
        self.assertNotIn(adult.id, lobby.pool)


class JoinLobbyTest(LobbyTestCase):
    def test_join_adds_member_once_and_bumps_version(self) -> None:
        lobby = self.create_open(members=[self.bob])
        version = lobby.version
        lobby = services.join_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.version, version + 1)
        self.assertEqual(lobby.memberships.filter(user=self.carol).get().role, LobbyMembership.Roles.MEMBER)
        lobby = services.join_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.version, version + 1)
        self.assertEqual(lobby.memberships.filter(user=self.carol).count(), 1)

    def test_join_rejects_ineligible_lobbies(self) -> None:
        with self.assertRaises(NotJoinableError):
            services.join_lobby(self.create_group().uuid, self.dave)
        started = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(NotJoinableError):
            services.join_lobby(started.uuid, self.carol)
        with self.assertRaises(LobbyNotFoundError):
            services.join_lobby(uuid4(), self.alice)


class AuthTest(LobbyTestCase):
    def test_non_member_cannot_read_or_mutate(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        actions = (
            ("vote", lambda: services.vote(lobby.uuid, self.dave, lobby.pool[0], engine.INTERESTED)),
            ("ready", lambda: services.mark_ready(lobby.uuid, self.dave)),
            ("pick", lambda: services.pick(lobby.uuid, self.dave, lobby.pool[0])),
            ("state", lambda: services.get_state(lobby.uuid, self.dave)),
            ("lobby", lambda: services.get_lobby_for_member(lobby.uuid, self.dave)),
        )
        for name, action in actions:
            with self.subTest(name=name), self.assertRaises(NotAMemberError):
                action()

    def test_non_host_cannot_run_host_commands(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        actions = (
            ("advance", lambda: services.advance(lobby.uuid, self.bob)),
            ("finalize", lambda: services.finalize_lobby(lobby.uuid, self.bob)),
            ("end", lambda: services.end_lobby(lobby.uuid, self.bob)),
        )
        for name, action in actions:
            with self.subTest(name=name), self.assertRaises(NotHostError):
                action()


class StateValidationTest(LobbyTestCase):
    def test_mark_ready_requires_ready_state(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.mark_ready(lobby.uuid, self.alice)

    def test_vote_requires_playing_state(self) -> None:
        ready = self.create_open(members=[self.bob])
        with self.assertRaises(InvalidStateError):
            services.vote(ready.uuid, self.alice, ready.pool[0], engine.INTERESTED)
        final = self.play_to_final(self.start(ready, [self.alice, self.bob]))
        with self.assertRaises(InvalidStateError):
            services.vote(final.uuid, self.alice, final.finalists[0], engine.INTERESTED)

    def test_pick_requires_final_round(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.pick(lobby.uuid, self.alice, lobby.pool[0])

    def test_host_commands_require_their_status(self) -> None:
        ready = self.create_open(members=[self.bob])
        with self.assertRaises(InvalidStateError):
            services.advance(ready.uuid, self.alice)

        playing = self.start(ready, [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.finalize_lobby(playing.uuid, self.alice)

        final = self.play_to_final(playing)
        with self.assertRaises(InvalidStateError):
            services.advance(final.uuid, self.alice)
        services.finalize_lobby(final.uuid, self.alice)
        with self.assertRaises(InvalidStateError):
            services.finalize_lobby(final.uuid, self.alice)

    def test_invalid_choice_and_non_finalist_pick_are_rejected(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidChoiceError):
            services.vote(lobby.uuid, self.alice, lobby.pool[0], "maybe")
        final = self.play_to_final(lobby)
        with self.assertRaises(InvalidChoiceError):
            services.pick(final.uuid, self.alice, 999_999)


class VersionTest(LobbyTestCase):
    def test_ready_start_and_end_bump_once(self) -> None:
        lobby = self.create_open(members=[self.bob])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 1)
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 1)
        lobby = services.mark_ready(lobby.uuid, self.bob)
        self.assertEqual(lobby.version, 2)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 3)
        lobby = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 3)

    def test_vote_bumps_only_on_change(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        version = lobby.version
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        self.assertEqual(lobby.version, version + 1)
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        self.assertEqual(lobby.version, version + 1)
        lobby = services.vote(lobby.uuid, self.alice, current, engine.WATCHED)
        self.assertEqual(lobby.version, version + 2)

    def test_pick_bumps_only_on_change(self) -> None:
        lobby = self.play_to_final(self.start(self.create_open(members=[self.bob]), [self.alice, self.bob]))
        version = lobby.version
        lobby = services.pick(lobby.uuid, self.alice, lobby.finalists[0])
        self.assertEqual(lobby.version, version + 1)
        lobby = services.pick(lobby.uuid, self.alice, lobby.finalists[0])
        self.assertEqual(lobby.version, version + 1)
        lobby = services.pick(lobby.uuid, self.alice, lobby.finalists[1])
        self.assertEqual(lobby.version, version + 2)

    def test_finalize_bumps_version(self) -> None:
        lobby = self.play_to_final(self.start(self.create_open(members=[self.bob]), [self.alice, self.bob]))
        version = lobby.version
        lobby = services.finalize_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, version + 1)


class GameFlowTest(LobbyTestCase):
    def test_full_game_to_winner(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start(self.create_open(members=users), users)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertIsNotNone(lobby.started_at)
        lobby = self.play_to_final(lobby, users)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertEqual(len(lobby.finalists), engine.FINALIST_COUNT)
        winner = lobby.finalists[0]
        lobby = self.pick_for_all(lobby, winner)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertEqual(lobby.winner_movie_id, winner)
        self.assertIsNotNone(lobby.finished_at)

    def test_stale_vote_and_unknown_movie_are_noops(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start(self.create_open(members=users), users)
        first = lobby.pool[0]
        lobby = self.vote_current(lobby, users)
        self.assertIn(first, lobby.finalists)
        expected_votes = {str(user.pk): engine.INTERESTED for user in users}
        version = lobby.version
        lobby = services.vote(lobby.uuid, self.alice, first, engine.WATCHED)
        self.assertEqual(lobby.votes[str(first)], expected_votes)
        self.assertEqual(lobby.pool_index, 1)
        self.assertEqual(lobby.version, version)
        lobby = services.vote(lobby.uuid, self.alice, 999_999, engine.INTERESTED)
        self.assertEqual(lobby.version, version)

    def test_force_advance_skips_current_without_a_finalist(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start(self.create_open(members=users), users)
        current = lobby.pool[0]
        lobby = services.advance(lobby.uuid, self.alice)
        self.assertEqual(lobby.pool_index, 1)
        self.assertNotIn(current, lobby.finalists)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)

    def test_vote_exhaustion_with_finalists_enters_final_round(self) -> None:
        lobby = services.create_lobby(self.dave, [], pool_size=2)
        lobby = services.mark_ready(lobby.uuid, self.dave)
        lobby = services.vote(lobby.uuid, self.dave, lobby.pool[0], engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.dave, lobby.pool[1], engine.WATCHED)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertEqual(len(lobby.finalists), 1)

    def test_vote_exhaustion_without_finalists_finishes(self) -> None:
        lobby = services.create_lobby(self.dave, [], pool_size=2)
        lobby = services.mark_ready(lobby.uuid, self.dave)
        lobby = services.vote(lobby.uuid, self.dave, lobby.pool[0], engine.WATCHED)
        lobby = services.vote(lobby.uuid, self.dave, lobby.pool[1], engine.WATCHED)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertEqual(lobby.finalists, [])
        self.assertIsNotNone(lobby.finished_at)

    def test_empty_pool_finishes_when_ready(self) -> None:
        lobby = services.create_lobby(self.alice, [], pool=[])
        version = lobby.version
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertIsNone(lobby.started_at)
        self.assertIsNotNone(lobby.finished_at)
        self.assertEqual(lobby.version, version + 1)

    def test_finalize_without_or_with_partial_picks(self) -> None:
        no_picks = self.play_to_final(self.start(self.create_open(members=[self.bob]), [self.alice, self.bob]))
        no_picks = services.finalize_lobby(no_picks.uuid, self.alice)
        self.assertEqual(no_picks.status, Lobby.Status.FINISHED)
        self.assertIsNone(no_picks.winner_movie_id)

        partial = self.play_to_final(self.start(self.create_open(members=[self.bob]), [self.alice, self.bob]))
        winner = partial.finalists[0]
        partial = services.pick(partial.uuid, self.alice, winner)
        partial = services.finalize_lobby(partial.uuid, self.alice)
        self.assertEqual(partial.status, Lobby.Status.FINISHED)
        self.assertEqual(partial.winner_movie_id, winner)

    def test_end_clears_active_lobbies_without_a_winner(self) -> None:
        ready = self.create_open(members=[self.bob])
        playing = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        final = self.play_to_final(self.start(self.create_open(members=[self.bob]), [self.alice, self.bob]))
        for name, lobby in (("ready", ready), ("playing", playing), ("final", final)):
            with self.subTest(name=name):
                ended = services.end_lobby(lobby.uuid, self.alice)
                self.assertEqual(ended.status, Lobby.Status.FINISHED)
                self.assertIsNone(ended.winner_movie_id)
                self.assertIsNotNone(ended.finished_at)


class LeaveTest(LobbyTestCase):
    def test_leave_removes_member_and_prunes_votes(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start(self.create_open(members=users), users)
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        version = lobby.version
        lobby = services.leave_lobby(lobby.uuid, self.bob)
        self.assertEqual(lobby.memberships.count(), 2)
        self.assertNotIn(str(self.bob.pk), lobby.ready)
        self.assertNotIn(str(self.bob.pk), lobby.votes.get(str(current), {}))
        self.assertEqual(lobby.version, version + 1)
        lobby = services.vote(lobby.uuid, self.carol, current, engine.INTERESTED)
        self.assertIn(current, lobby.finalists)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)

    def test_leave_completes_the_current_round_immediately(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start(self.create_open(members=users), users)
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertIn(current, lobby.finalists)
        self.assertEqual(lobby.pool_index, 1)

    def test_leave_can_start_the_game(self) -> None:
        lobby = self.create_open(members=[self.bob, self.carol])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        lobby = services.mark_ready(lobby.uuid, self.bob)
        self.assertEqual(lobby.status, Lobby.Status.READY)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertIsNotNone(lobby.started_at)

    def test_leave_can_resolve_the_final_round(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.play_to_final(self.start(self.create_open(members=users), users), users)
        winner = lobby.finalists[0]
        lobby = services.pick(lobby.uuid, self.alice, winner)
        lobby = services.pick(lobby.uuid, self.bob, winner)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertEqual(lobby.winner_movie_id, winner)

    def test_leave_records_a_group_winner(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.play_to_final(self.start(self.create_group(), users), users)
        winner = lobby.finalists[0]
        lobby = services.pick(lobby.uuid, self.alice, winner)
        lobby = services.pick(lobby.uuid, self.bob, winner)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertEqual(lobby.winner_movie_id, winner)
        group_movie = GroupMovie.objects.get(group=self.group, movie_id=winner)
        self.assertEqual(group_movie.status, GroupMovie.Status.SUGGESTED)
        self.assertEqual(group_movie.suggested_by_id, self.alice.id)

    def test_leave_rejects_host_non_member_and_finished(self) -> None:
        lobby = self.create_open(members=[self.bob])
        with self.assertRaises(NotAMemberError):
            services.leave_lobby(lobby.uuid, self.alice)
        with self.assertRaises(NotAMemberError):
            services.leave_lobby(lobby.uuid, self.dave)
        services.end_lobby(lobby.uuid, self.alice)
        with self.assertRaises(InvalidStateError):
            services.leave_lobby(lobby.uuid, self.bob)


class GroupWinnerTest(LobbyTestCase):
    def test_group_winner_is_added_as_suggested(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.play_to_final(self.start(self.create_group(), users), users)
        winner = lobby.finalists[0]
        lobby = self.pick_for_all(lobby, winner)
        self.assertEqual(lobby.winner_movie_id, winner)
        group_movie = GroupMovie.objects.get(group=self.group, movie_id=winner)
        self.assertEqual(group_movie.status, GroupMovie.Status.SUGGESTED)
        self.assertEqual(group_movie.suggested_by_id, self.alice.id)

    def test_existing_group_movie_is_preserved(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.play_to_final(self.start(self.create_group(), users), users)
        winner = lobby.finalists[0]
        existing = GroupMovie.objects.create(group=self.group, movie_id=winner, suggested_by=self.bob)
        self.pick_for_all(lobby, winner)
        existing.refresh_from_db()
        self.assertEqual(existing.suggested_by_id, self.bob.id)
        self.assertEqual(GroupMovie.objects.filter(group=self.group, movie_id=winner).count(), 1)

    def test_open_and_winnerless_group_lobbies_add_nothing(self) -> None:
        users = [self.alice, self.bob]
        open_lobby = self.play_to_final(self.start(self.create_open(members=users), users), users)
        self.pick_for_all(open_lobby, open_lobby.finalists[0])
        group_lobby = self.play_to_final(
            self.start(self.create_group(), [self.alice, self.bob, self.carol]),
            [self.alice, self.bob, self.carol],
        )
        services.finalize_lobby(group_lobby.uuid, self.alice)
        self.assertEqual(GroupMovie.objects.count(), 0)


class ReadModelTest(LobbyTestCase):
    def test_state_vote_privacy_and_progress(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start(self.create_open(members=users), users)
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

    def test_ready_state_lists_players_and_ready_flags(self) -> None:
        lobby = self.create_open(members=[self.bob])
        services.mark_ready(lobby.uuid, self.alice)
        state = services.get_state(lobby.uuid, self.alice)
        self.assertEqual(state.players[0].user_id, self.alice.id)
        self.assertTrue(state.players[0].is_host)
        self.assertTrue(state.players[0].is_ready)
        self.assertFalse(state.players[1].is_ready)
        self.assertEqual(state.status, Lobby.Status.READY)
        self.assertEqual(state.submitted_count, 0)
        self.assertIsNone(state.viewer_vote)

    def test_state_pick_privacy_and_counts(self) -> None:
        users = [self.alice, self.bob]
        lobby = self.play_to_final(self.start(self.create_open(members=users), users), users)
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

    def test_state_exposes_group_winner_and_timestamps(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.play_to_final(self.start(self.create_group(), users), users)
        winner = lobby.finalists[0]
        self.pick_for_all(lobby, winner)
        state = services.get_state(lobby.uuid, self.alice)
        self.assertEqual(state.group_uuid, self.group.uuid)
        self.assertEqual(state.group_name, self.group.name)
        self.assertEqual(state.winner.id, winner)
        self.assertEqual(state.status, Lobby.Status.FINISHED)
        self.assertIsNotNone(state.started_at)
        self.assertIsNotNone(state.finished_at)

    def test_state_uses_a_constant_number_of_queries(self) -> None:
        lobby = self.start(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertNumQueries(3):
            services.get_state(lobby.uuid, self.alice)

    def test_reads_require_membership(self) -> None:
        lobby = self.create_open(members=[self.bob])
        with self.assertRaises(NotAMemberError):
            services.get_state(lobby.uuid, self.dave)
        with self.assertRaises(NotAMemberError):
            services.get_lobby_for_member(lobby.uuid, self.dave)
        self.assertEqual(services.get_lobby_for_member(lobby.uuid, self.bob).pk, lobby.pk)

    def test_active_group_lobby(self) -> None:
        lobby = self.create_group()
        self.assertEqual(services.get_active_group_lobby(self.group).pk, lobby.pk)
        services.end_lobby(lobby.uuid, self.alice)
        self.assertIsNone(services.get_active_group_lobby(self.group))


class ConstraintTest(LobbyTestCase):
    def test_unique_active_lobby_per_group(self) -> None:
        self.create_group()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lobby.objects.create(type=Lobby.Type.GROUP, group=self.group, host=self.bob)

    def test_lobby_type_must_match_group(self) -> None:
        cases = ((Lobby.Type.GROUP, None), (Lobby.Type.OPEN, self.group))
        for lobby_type, group in cases:
            with self.subTest(lobby_type=lobby_type), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Lobby.objects.create(type=lobby_type, group=group, host=self.alice)

    def test_membership_is_unique_per_lobby_and_host_is_unique(self) -> None:
        lobby = Lobby.objects.create(type=Lobby.Type.OPEN, host=self.alice)
        LobbyMembership.objects.create(lobby=lobby, user=self.alice, role=LobbyMembership.Roles.HOST)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyMembership.objects.create(lobby=lobby, user=self.alice, role=LobbyMembership.Roles.MEMBER)

        other = Lobby.objects.create(type=Lobby.Type.OPEN, host=self.alice)
        LobbyMembership.objects.create(lobby=other, user=self.alice, role=LobbyMembership.Roles.HOST)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyMembership.objects.create(lobby=other, user=self.bob, role=LobbyMembership.Roles.HOST)


class ErrorContractTest(LobbyTestCase):
    def test_unknown_lobby_raises_not_found(self) -> None:
        with self.assertRaises(LobbyNotFoundError):
            services.mark_ready(uuid4(), self.alice)


if __name__ == "__main__":
    main()
