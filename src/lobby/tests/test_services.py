from collections.abc import Iterable
from unittest import main
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase as DjangoTestCase

from groups.models import Group, GroupMovie
from lobby import engine, rules, selectors, services
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

    def start_all(self, lobby: Lobby, users: Iterable[User] | None = None) -> Lobby:
        for user in self.members(lobby) if users is None else users:
            lobby = services.mark_ready(lobby.uuid, user)
        return services.start_lobby(lobby.uuid, User.objects.get(pk=lobby.host_id))

    def start_with(self, lobby: Lobby, users: Iterable[User]) -> Lobby:
        for user in users:
            lobby = services.mark_ready(lobby.uuid, user)
        return services.start_lobby(lobby.uuid, User.objects.get(pk=lobby.host_id))

    def vote_current(self, lobby: Lobby, users: Iterable[User], choice: str = engine.INTERESTED) -> Lobby:
        current = lobby.pool[lobby.pool_index]
        for user in users:
            lobby = services.vote(lobby.uuid, user, current, choice)
        return lobby

    def play_to_final(self, lobby: Lobby, users: Iterable[User] | None = None) -> Lobby:
        voters = list(users) if users is not None else self.members(lobby)
        while lobby.status == Lobby.Status.PLAYING:
            if lobby.revealed:
                lobby = services.next_round(lobby.uuid, voters[0])
            else:
                lobby = self.vote_current(lobby, voters)
        return lobby

    def pick_for_all(self, lobby: Lobby, movie_id: int) -> Lobby:
        for user in self.members(lobby):
            lobby = services.pick(lobby.uuid, user, movie_id)
        return lobby

    def finish(self, lobby: Lobby, users: Iterable[User] | None = None) -> Lobby:
        lobby = self.play_to_final(lobby, users)
        winner = lobby.finalists[0]
        lobby = self.pick_for_all(lobby, winner)
        return services.finalize_lobby(lobby.uuid, self.alice)


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
        self.assertFalse(lobby.revealed)
        self.assertFalse(lobby.picks_revealed)
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
        started = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(NotJoinableError):
            services.join_lobby(started.uuid, self.carol)
        with self.assertRaises(LobbyNotFoundError):
            services.join_lobby(uuid4(), self.alice)


class AuthTest(LobbyTestCase):
    def test_non_member_cannot_read_or_mutate(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        actions = (
            ("vote", lambda: services.vote(lobby.uuid, self.dave, lobby.pool[0], engine.INTERESTED)),
            ("ready", lambda: services.mark_ready(lobby.uuid, self.dave)),
            ("unready", lambda: services.unready(lobby.uuid, self.dave)),
            ("start", lambda: services.start_lobby(lobby.uuid, self.dave)),
            ("pick", lambda: services.pick(lobby.uuid, self.dave, lobby.pool[0])),
            ("state", lambda: services.get_state(lobby.uuid, self.dave)),
            ("lobby", lambda: services.get_lobby_for_member(lobby.uuid, self.dave)),
            ("restart", lambda: services.restart_lobby(lobby.uuid, self.dave)),
        )
        for name, action in actions:
            with self.subTest(name=name), self.assertRaises((NotAMemberError, NotHostError)):
                action()

    def test_non_host_cannot_run_host_commands(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        actions = (
            ("advance", lambda: services.advance(lobby.uuid, self.bob)),
            ("finalize", lambda: services.finalize_lobby(lobby.uuid, self.bob)),
            ("end", lambda: services.end_lobby(lobby.uuid, self.bob)),
        )
        for name, action in actions:
            with self.subTest(name=name), self.assertRaises((NotHostError, InvalidStateError)):
                action()


class StartTest(LobbyTestCase):
    def test_ready_does_not_start_the_game(self) -> None:
        lobby = self.create_open(members=[self.bob])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        lobby = services.mark_ready(lobby.uuid, self.bob)
        self.assertEqual(lobby.status, Lobby.Status.READY)
        self.assertIsNone(lobby.started_at)

    def test_host_start_keeps_only_ready_players(self) -> None:
        lobby = self.create_open(members=[self.bob, self.carol])
        lobby = services.mark_ready(lobby.uuid, self.bob)
        lobby = services.start_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertEqual(set(lobby.memberships.values_list("user_id", flat=True)), {self.alice.id, self.bob.id})
        self.assertIsNotNone(lobby.started_at)
        self.assertEqual(lobby.ready, sorted([str(self.alice.id), str(self.bob.id)], key=int))

    def test_host_is_included_even_when_not_ready(self) -> None:
        lobby = self.create_open(members=[self.bob])
        lobby = services.mark_ready(lobby.uuid, self.bob)
        lobby = services.start_lobby(lobby.uuid, self.alice)
        self.assertIn(self.alice.id, set(lobby.memberships.values_list("user_id", flat=True)))

    def test_unready_toggle_only_works_before_start(self) -> None:
        lobby = self.create_open(members=[self.bob])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        lobby = services.unready(lobby.uuid, self.alice)
        self.assertEqual(lobby.ready, [])
        with self.assertRaises(InvalidStateError):
            services.unready(self.start_all(lobby).uuid, self.alice)

    def test_non_host_and_non_ready_states_reject_start(self) -> None:
        lobby = self.create_open(members=[self.bob])
        with self.assertRaises(NotHostError):
            services.start_lobby(lobby.uuid, self.bob)
        started = self.start_all(lobby)
        with self.assertRaises(InvalidStateError):
            services.start_lobby(started.uuid, self.alice)

    def test_empty_pool_finishes_on_start(self) -> None:
        lobby = services.create_lobby(self.alice, [], pool=[])
        version = lobby.version
        lobby = services.start_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertIsNone(lobby.started_at)
        self.assertIsNotNone(lobby.finished_at)
        self.assertEqual(lobby.version, version + 1)


class StateValidationTest(LobbyTestCase):
    def test_mark_ready_requires_ready_state(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.mark_ready(lobby.uuid, self.alice)

    def test_vote_requires_playing_and_unrevealed(self) -> None:
        ready = self.create_open(members=[self.bob])
        with self.assertRaises(InvalidStateError):
            services.vote(ready.uuid, self.alice, ready.pool[0], engine.INTERESTED)
        playing = self.start_all(ready, [self.alice, self.bob])
        current = playing.pool[playing.pool_index]
        services.vote(playing.uuid, self.alice, current, engine.INTERESTED)
        revealed = services.vote(playing.uuid, self.bob, current, engine.INTERESTED)
        self.assertTrue(revealed.revealed)
        with self.assertRaises(InvalidStateError):
            services.vote(revealed.uuid, self.alice, current, engine.INTERESTED)

    def test_pick_requires_final_round_and_unrevealed(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.pick(lobby.uuid, self.alice, lobby.pool[0])
        final = self.play_to_final(lobby, [self.alice, self.bob])
        winner = final.finalists[0]
        final = self.pick_for_all(final, winner)
        self.assertTrue(final.picks_revealed)
        with self.assertRaises(InvalidStateError):
            services.pick(final.uuid, self.alice, winner)

    def test_advance_requires_host_playing_and_no_reveal(self) -> None:
        ready = self.create_open(members=[self.bob])
        with self.assertRaises(NotHostError):
            services.advance(ready.uuid, self.bob)
        with self.assertRaises(InvalidStateError):
            services.advance(ready.uuid, self.alice)

        playing = self.start_all(ready, [self.alice, self.bob])
        self.assertEqual(services.advance(playing.uuid, self.alice).pool_index, 1)

        revealed = self.vote_current(self.start_all(self.create_open(members=[self.bob])), [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.advance(revealed.uuid, self.alice)

    def test_next_round_requires_reveal(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidStateError):
            services.next_round(lobby.uuid, self.alice)
        revealed = self.vote_current(lobby, [self.alice, self.bob])
        next_lobby = services.next_round(revealed.uuid, self.bob)
        self.assertEqual(next_lobby.pool_index, 1)
        self.assertFalse(next_lobby.revealed)

    def test_finalize_permissions_and_state(self) -> None:
        final = self.play_to_final(self.start_all(self.create_open(members=[self.bob, self.carol])))
        winner = final.finalists[0]
        with self.assertRaises(NotHostError):
            services.finalize_lobby(final.uuid, self.bob)

        partial = services.pick(final.uuid, self.alice, winner)
        partial = services.finalize_lobby(partial.uuid, self.alice)
        self.assertEqual(partial.status, Lobby.Status.FINISHED)
        self.assertEqual(partial.winner_movie_id, winner)

    def test_any_member_can_finalize_after_all_picks(self) -> None:
        final = self.play_to_final(self.start_all(self.create_open(members=[self.bob])))
        final = self.pick_for_all(final, final.finalists[0])
        final = services.finalize_lobby(final.uuid, self.bob)
        self.assertEqual(final.status, Lobby.Status.FINISHED)

    def test_invalid_choice_and_non_finalist_pick_are_rejected(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertRaises(InvalidChoiceError):
            services.vote(lobby.uuid, self.alice, lobby.pool[0], "maybe")
        final = self.play_to_final(lobby)
        with self.assertRaises(InvalidChoiceError):
            services.pick(final.uuid, self.alice, 999_999)

    def test_end_requires_host_and_active_state(self) -> None:
        lobby = self.create_open(members=[self.bob])
        with self.assertRaises(NotHostError):
            services.end_lobby(lobby.uuid, self.bob)
        ended = services.end_lobby(lobby.uuid, self.alice)
        self.assertEqual(ended.status, Lobby.Status.FINISHED)
        self.assertIsNone(ended.winner_movie_id)
        self.assertIsNotNone(ended.finished_at)
        self.assertEqual(services.end_lobby(ended.uuid, self.alice).version, ended.version)


class VersionTest(LobbyTestCase):
    def test_each_meaningful_change_bumps_version_once(self) -> None:
        lobby = self.create_open(members=[self.bob])
        self.assertEqual(lobby.version, 0)
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 1)
        lobby = services.mark_ready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 1)
        lobby = services.unready(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 2)
        lobby = services.mark_ready(lobby.uuid, self.alice)
        lobby = services.mark_ready(lobby.uuid, self.bob)
        self.assertEqual(lobby.version, 4)
        lobby = services.start_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 5)

        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        self.assertEqual(lobby.version, 6)
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        self.assertEqual(lobby.version, 6)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        self.assertEqual(lobby.version, 7)
        self.assertTrue(lobby.revealed)
        lobby = services.next_round(lobby.uuid, self.alice)
        self.assertEqual(lobby.version, 8)

        final = self.play_to_final(lobby)
        version = final.version
        player_count = final.memberships.count()
        winner = final.finalists[0]
        final = self.pick_for_all(final, winner)
        self.assertEqual(final.version, version + player_count)
        self.assertTrue(final.picks_revealed)
        version = final.version
        final = services.finalize_lobby(final.uuid, self.alice)
        self.assertEqual(final.version, version + 1)
        self.assertEqual(services.end_lobby(final.uuid, self.alice).version, final.version)


class GameFlowTest(LobbyTestCase):
    def test_full_game_to_winner(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)
        self.assertIsNotNone(lobby.started_at)
        lobby = self.play_to_final(lobby, users)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertEqual(len(lobby.finalists), engine.FINALIST_COUNT)
        winner = lobby.finalists[0]
        lobby = self.pick_for_all(lobby, winner)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertTrue(lobby.picks_revealed)
        lobby = services.finalize_lobby(lobby.uuid, self.alice)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertEqual(lobby.winner_movie_id, winner)
        self.assertIsNotNone(lobby.finished_at)

    def test_all_votes_reveal_without_advancing(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        current = lobby.pool[0]
        lobby = self.vote_current(lobby, users)
        self.assertTrue(lobby.revealed)
        self.assertEqual(lobby.pool[lobby.pool_index], current)
        self.assertEqual(lobby.pool_index, 0)
        self.assertIn(current, lobby.finalists)
        lobby = services.next_round(lobby.uuid, self.alice)
        self.assertEqual(lobby.pool_index, 1)

    def test_stale_vote_and_unknown_movie_are_noops(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        first = lobby.pool[0]
        lobby = self.vote_current(lobby, users)
        expected_votes = {str(user.pk): engine.INTERESTED for user in users}
        lobby = services.next_round(lobby.uuid, self.alice)
        version = lobby.version
        lobby = services.vote(lobby.uuid, self.alice, first, engine.WATCHED)
        self.assertEqual(lobby.votes[str(first)], expected_votes)
        self.assertEqual(lobby.pool_index, 1)
        self.assertEqual(lobby.version, version)
        lobby = services.vote(lobby.uuid, self.alice, 999_999, engine.INTERESTED)
        self.assertEqual(lobby.version, version)

    def test_force_advance_skips_current_without_a_finalist(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        current = lobby.pool[0]
        lobby = services.advance(lobby.uuid, self.alice)
        self.assertEqual(lobby.pool_index, 1)
        self.assertNotIn(current, lobby.finalists)
        self.assertEqual(lobby.status, Lobby.Status.PLAYING)

    def test_vote_exhaustion_with_finalists_enters_final_round(self) -> None:
        lobby = services.create_lobby(self.dave, [], pool_size=2)
        lobby = self.start_all(lobby)
        lobby = self.vote_current(lobby, [self.dave])
        lobby = services.next_round(lobby.uuid, self.dave)
        lobby = self.vote_current(lobby, [self.dave], engine.WATCHED)
        lobby = services.next_round(lobby.uuid, self.dave)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        self.assertEqual(len(lobby.finalists), 1)

    def test_vote_exhaustion_without_finalists_finishes(self) -> None:
        lobby = services.create_lobby(self.dave, [], pool_size=2)
        lobby = self.start_all(lobby)
        lobby = self.vote_current(lobby, [self.dave], engine.WATCHED)
        lobby = services.next_round(lobby.uuid, self.dave)
        lobby = self.vote_current(lobby, [self.dave], engine.WATCHED)
        lobby = services.next_round(lobby.uuid, self.dave)
        self.assertEqual(lobby.status, Lobby.Status.FINISHED)
        self.assertIsNone(lobby.winner_movie_id)
        self.assertEqual(lobby.finalists, [])
        self.assertIsNotNone(lobby.finished_at)

    def test_finalize_without_or_with_partial_picks(self) -> None:
        no_picks = self.play_to_final(self.start_all(self.create_open(members=[self.bob])))
        no_picks = services.finalize_lobby(no_picks.uuid, self.alice)
        self.assertEqual(no_picks.status, Lobby.Status.FINISHED)
        self.assertIsNone(no_picks.winner_movie_id)

        partial = self.play_to_final(self.start_all(self.create_open(members=[self.bob])))
        winner = partial.finalists[0]
        partial = services.pick(partial.uuid, self.alice, winner)
        partial = services.finalize_lobby(partial.uuid, self.alice)
        self.assertEqual(partial.status, Lobby.Status.FINISHED)
        self.assertEqual(partial.winner_movie_id, winner)

    def test_end_clears_active_lobbies_without_a_winner(self) -> None:
        ready = self.create_open(members=[self.bob])
        playing = self.start_all(self.create_open(members=[self.bob]))
        final = self.play_to_final(self.start_all(self.create_open(members=[self.bob, self.carol])))
        for name, lobby in (("ready", ready), ("playing", playing), ("final", final)):
            with self.subTest(name=name):
                ended = services.end_lobby(lobby.uuid, self.alice)
                self.assertEqual(ended.status, Lobby.Status.FINISHED)
                self.assertIsNone(ended.winner_movie_id)
                self.assertIsNotNone(ended.finished_at)


class LeaveTest(LobbyTestCase):
    def test_leave_removes_member_and_prunes_votes(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.carol, current, engine.INTERESTED)
        lobby = services.next_round(lobby.uuid, self.alice)
        current = lobby.pool[lobby.pool_index]
        for user in users:
            lobby = services.vote(lobby.uuid, user, current, engine.INTERESTED)
        version = lobby.version
        lobby = services.leave_lobby(lobby.uuid, self.bob)
        self.assertEqual(lobby.memberships.count(), 2)
        self.assertNotIn(str(self.bob.pk), lobby.ready)
        self.assertNotIn(str(self.bob.pk), lobby.votes.get(str(current), {}))
        self.assertEqual(lobby.version, version + 1)
        self.assertTrue(lobby.revealed)
        self.assertIn(current, lobby.finalists)

    def test_leave_can_reveal_the_current_round(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        current = lobby.pool[lobby.pool_index]
        lobby = services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        lobby = services.vote(lobby.uuid, self.bob, current, engine.INTERESTED)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertTrue(lobby.revealed)
        self.assertIn(current, lobby.finalists)

    def test_leave_during_ready_does_not_start_the_game(self) -> None:
        lobby = self.create_open(members=[self.bob, self.carol])
        lobby = services.mark_ready(lobby.uuid, self.alice)
        lobby = services.mark_ready(lobby.uuid, self.bob)
        lobby = services.leave_lobby(lobby.uuid, self.carol)
        self.assertEqual(lobby.status, Lobby.Status.READY)
        self.assertEqual(lobby.memberships.count(), 2)

    def test_leave_can_reveal_the_final_picks(self) -> None:
        users = [self.alice, self.bob, self.carol]
        final = self.play_to_final(self.start_all(self.create_open(members=users), users), users)
        winner = final.finalists[0]
        final = services.pick(final.uuid, self.alice, winner)
        final = services.pick(final.uuid, self.bob, winner)
        final = services.leave_lobby(final.uuid, self.carol)
        self.assertEqual(final.status, Lobby.Status.FINAL_ROUND)
        self.assertTrue(final.picks_revealed)
        self.assertIsNone(final.winner_movie_id)
        final = services.finalize_lobby(final.uuid, self.alice)
        self.assertEqual(final.winner_movie_id, winner)

    def test_leave_rejects_host_non_member_and_finished(self) -> None:
        lobby = self.create_open(members=[self.bob])
        with self.assertRaises(NotAMemberError):
            services.leave_lobby(lobby.uuid, self.alice)
        with self.assertRaises(NotAMemberError):
            services.leave_lobby(lobby.uuid, self.dave)
        services.end_lobby(lobby.uuid, self.alice)
        with self.assertRaises(InvalidStateError):
            services.leave_lobby(lobby.uuid, self.bob)


class RestartTest(LobbyTestCase):
    def test_group_restart_creates_a_ready_lobby_with_current_group_members(self) -> None:
        users = [self.alice, self.bob, self.carol]
        finished = self.finish(self.start_all(self.create_group(), users), users)
        self.assertEqual(finished.status, Lobby.Status.FINISHED)
        new_lobby = services.restart_lobby(finished.uuid, self.alice)
        self.assertNotEqual(new_lobby.pk, finished.pk)
        self.assertEqual(new_lobby.status, Lobby.Status.READY)
        self.assertEqual(new_lobby.type, Lobby.Type.GROUP)
        self.assertEqual(
            set(new_lobby.memberships.values_list("user_id", flat=True)), {self.alice.id, self.bob.id, self.carol.id}
        )
        self.assertEqual(services.get_active_group_lobby(self.group).pk, new_lobby.pk)

    def test_open_restart_copies_current_members(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]))
        services.end_lobby(lobby.uuid, self.alice)
        new_lobby = services.restart_lobby(lobby.uuid, self.alice)
        self.assertEqual(new_lobby.status, Lobby.Status.READY)
        self.assertEqual(new_lobby.type, Lobby.Type.OPEN)
        self.assertEqual(set(new_lobby.memberships.values_list("user_id", flat=True)), {self.alice.id, self.bob.id})

    def test_restart_requires_host_and_finished_state(self) -> None:
        lobby = self.create_open(members=[self.bob])
        with self.assertRaises(NotHostError):
            services.restart_lobby(lobby.uuid, self.bob)
        with self.assertRaises(InvalidStateError):
            services.restart_lobby(lobby.uuid, self.alice)
        services.end_lobby(lobby.uuid, self.alice)
        with self.assertRaises(NotHostError):
            services.restart_lobby(lobby.uuid, self.bob)


class GroupWinnerTest(LobbyTestCase):
    def test_group_winner_is_added_as_suggested(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.finish(self.start_all(self.create_group(), users), users)
        winner = lobby.winner_movie_id
        self.assertIsNotNone(winner)
        group_movie = GroupMovie.objects.get(group=self.group, movie_id=winner)
        self.assertEqual(group_movie.status, GroupMovie.Status.SUGGESTED)
        self.assertEqual(group_movie.suggested_by_id, self.alice.id)

    def test_existing_group_movie_is_preserved(self) -> None:
        users = [self.alice, self.bob, self.carol]
        candidates = self.play_to_final(self.start_all(self.create_group(), users), users)
        winner = candidates.finalists[0]
        existing = GroupMovie.objects.create(group=self.group, movie_id=winner, suggested_by=self.bob)
        lobby = self.pick_for_all(candidates, winner)
        services.finalize_lobby(lobby.uuid, self.alice)
        existing.refresh_from_db()
        self.assertEqual(existing.suggested_by_id, self.bob.id)
        self.assertEqual(GroupMovie.objects.filter(group=self.group, movie_id=winner).count(), 1)

    def test_open_and_winnerless_group_lobbies_add_nothing(self) -> None:
        users = [self.alice, self.bob]
        open_lobby = self.finish(self.start_all(self.create_open(members=users), users), users)
        self.assertIsNotNone(open_lobby.winner_movie_id)
        group_lobby = self.play_to_final(self.start_all(self.create_group(), users), users)
        services.finalize_lobby(group_lobby.uuid, self.alice)
        self.assertEqual(GroupMovie.objects.count(), 0)


class ReadModelTest(LobbyTestCase):
    def test_state_vote_privacy_until_reveal(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        current = lobby.pool[lobby.pool_index]
        services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        services.vote(lobby.uuid, self.bob, current, engine.WATCHED)
        alice_state = services.get_state(lobby.uuid, self.alice)
        bob_state = services.get_state(lobby.uuid, self.bob)
        self.assertEqual(alice_state.viewer_vote, engine.INTERESTED)
        self.assertEqual(bob_state.viewer_vote, engine.WATCHED)
        self.assertEqual(alice_state.submitted_count, 2)
        self.assertEqual(alice_state.player_count, 3)
        self.assertFalse(alice_state.revealed)
        self.assertIsNone(alice_state.vote_tally)
        self.assertEqual(alice_state.ballot, ())
        self.assertEqual(alice_state.current_movie.id, current)
        self.assertTrue(alice_state.viewer_is_host)
        self.assertFalse(bob_state.viewer_is_host)

    def test_state_exposes_tally_and_ballot_after_reveal(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.start_all(self.create_open(members=users), users)
        current = lobby.pool[lobby.pool_index]
        services.vote(lobby.uuid, self.alice, current, engine.INTERESTED)
        services.vote(lobby.uuid, self.bob, current, engine.WATCHED)
        services.vote(lobby.uuid, self.carol, current, engine.NOT_INTERESTED)
        state = services.get_state(lobby.uuid, self.alice)
        self.assertTrue(state.revealed)
        self.assertEqual(state.vote_tally.interested, 1)
        self.assertEqual(state.vote_tally.watched, 1)
        self.assertEqual(state.vote_tally.not_interested, 1)
        self.assertEqual({entry.user_id for entry in state.ballot}, {user.id for user in users})
        self.assertTrue(state.capabilities.can_next_round)
        self.assertFalse(state.capabilities.can_advance)

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
        self.assertEqual(state.ready_count, 1)
        self.assertTrue(state.viewer_ready)
        self.assertTrue(state.capabilities.can_start)
        self.assertTrue(state.capabilities.can_unready)

    def test_state_pick_privacy_and_counts(self) -> None:
        users = [self.alice, self.bob]
        lobby = self.play_to_final(self.start_all(self.create_open(members=users), users), users)
        winner = lobby.finalists[0]
        services.pick(lobby.uuid, self.alice, winner)
        alice_state = services.get_state(lobby.uuid, self.alice)
        bob_state = services.get_state(lobby.uuid, self.bob)
        self.assertEqual(alice_state.viewer_pick, winner)
        self.assertIsNone(bob_state.viewer_pick)
        self.assertTrue(alice_state.finalists[0].viewer_picked)
        self.assertFalse(bob_state.finalists[0].viewer_picked)
        self.assertIsNone(bob_state.finalists[0].pick_count)
        self.assertEqual(bob_state.submitted_count, 1)
        self.assertFalse(bob_state.picks_revealed)

        services.pick(lobby.uuid, self.bob, winner)
        revealed = services.get_state(lobby.uuid, self.bob)
        self.assertTrue(revealed.picks_revealed)
        self.assertEqual(revealed.finalists[0].pick_count, 2)
        self.assertIsNone(revealed.winner)
        self.assertTrue(revealed.capabilities.can_finalize)

    def test_state_exposes_group_winner_and_timestamps(self) -> None:
        users = [self.alice, self.bob, self.carol]
        lobby = self.finish(self.start_all(self.create_group(), users), users)
        state = services.get_state(lobby.uuid, self.alice)
        self.assertEqual(state.group_uuid, self.group.uuid)
        self.assertEqual(state.group_name, self.group.name)
        self.assertEqual(state.winner.id, lobby.winner_movie_id)
        self.assertEqual(state.status, Lobby.Status.FINISHED)
        self.assertIsNotNone(state.started_at)
        self.assertIsNotNone(state.finished_at)
        self.assertTrue(state.capabilities.can_restart)

    def test_state_uses_a_constant_number_of_queries(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        with self.assertNumQueries(3):
            services.get_state(lobby.uuid, self.alice)

    def test_join_preview_reflects_membership_and_type(self) -> None:
        open_lobby = self.create_open(members=[self.bob])
        preview = selectors.get_join_preview(open_lobby.uuid, self.carol)
        self.assertTrue(preview.can_join)
        self.assertFalse(preview.is_member)
        self.assertEqual(preview.player_count, 2)

        preview = selectors.get_join_preview(open_lobby.uuid, self.alice)
        self.assertFalse(preview.can_join)
        self.assertTrue(preview.is_member)

        group_lobby = self.create_group()
        preview = selectors.get_join_preview(group_lobby.uuid, self.dave)
        self.assertFalse(preview.can_join)
        self.assertFalse(preview.is_member)

    def test_active_lobby_summary(self) -> None:
        lobby = self.start_all(self.create_open(members=[self.bob]), [self.alice, self.bob])
        summary = selectors.get_active_lobby_for_user(self.alice)
        self.assertIsNotNone(summary)
        self.assertEqual(summary.uuid, lobby.uuid)
        self.assertEqual(summary.player_count, 2)
        self.assertEqual(summary.current_movie_title, Movie.objects.get(pk=lobby.pool[0]).title)
        services.end_lobby(lobby.uuid, self.alice)
        self.assertIsNone(selectors.get_active_lobby_for_user(self.alice))

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
