import unittest
from dataclasses import replace

from lobby.engine import (
    FINALIST_COUNT,
    FINISHED,
    FINAL_ROUND,
    INTERESTED,
    NOT_INTERESTED,
    PLAYING,
    READY,
    WATCHED,
    Game,
    advance,
    end,
    finalize,
    mark_ready,
    new_game,
    pick,
    reconcile,
    vote,
)
from lobby.exceptions import InvalidChoiceError


def players_and_pool():
    return list("abc"), list(range(10))


def vote_on_current(game: Game, user: str, choice: str) -> Game:
    if game.current is None:
        raise AssertionError("expected a current movie")
    return vote(game, user, game.current, choice)


def unanimous_interested(game: Game) -> Game:
    for user in sorted(game.players):
        if game.current is None:
            break
        game = vote(game, user, game.current, INTERESTED)
    return game


def make_final_round(players, candidates):
    return Game(
        status=FINAL_ROUND,
        players=frozenset(players),
        ready=frozenset(players),
        pool=(),
        pool_index=0,
        current=None,
        votes={},
        picks={},
        candidates=tuple(candidates),
        winner=None,
    )


class NewGameTest(unittest.TestCase):
    def test_initial_state(self):
        players, pool = players_and_pool()
        game = new_game(players, pool)
        self.assertEqual(game.status, READY)
        self.assertEqual(game.players, frozenset(players))
        self.assertEqual(game.ready, frozenset())
        self.assertEqual(game.pool, tuple(pool))
        self.assertEqual(game.pool_index, 0)
        self.assertIsNone(game.current)
        self.assertEqual(game.candidates, ())
        self.assertIsNone(game.winner)


class MarkReadyTest(unittest.TestCase):
    def setUp(self):
        self.players, self.pool = players_and_pool()
        self.game = new_game(self.players, self.pool)

    def test_marks_ready_and_stays_ready(self):
        g = mark_ready(self.game, "a")
        self.assertEqual(g.status, READY)
        self.assertIn("a", g.ready)

    def test_starts_when_everyone_is_ready(self):
        g = mark_ready(self.game, "a")
        g = mark_ready(g, "b")
        self.assertEqual(g.status, READY)
        g = mark_ready(g, "c")
        self.assertEqual(g.status, PLAYING)
        self.assertEqual(g.current, self.pool[0])

    def test_noop_in_non_ready_state(self):
        g = mark_ready(self.game, "a")
        g = mark_ready(g, "b")
        g = mark_ready(g, "c")
        g2 = mark_ready(g, "a")
        self.assertEqual(g2.status, PLAYING)
        self.assertEqual(g2.current, self.pool[0])
        self.assertEqual(g2.ready, g.ready)


class VoteTest(unittest.TestCase):
    def setUp(self):
        self.players, self.pool = players_and_pool()
        self.game = new_game(self.players, self.pool)
        for u in "ab":
            self.game = mark_ready(self.game, u)
        self.game = mark_ready(self.game, "c")

    def test_records_vote_without_deciding(self):
        g = vote_on_current(self.game, "a", INTERESTED)
        self.assertEqual(g.status, PLAYING)
        self.assertEqual(g.current, self.pool[0])
        self.assertEqual(g.votes[self.pool[0]], {"a": INTERESTED})

    def test_unanimous_interested_advances_and_nexts(self):
        g = unanimous_interested(self.game)
        self.assertIn(self.pool[0], g.candidates)
        self.assertEqual(g.current, self.pool[1])
        self.assertEqual(g.status, PLAYING)
        self.assertEqual(g.candidates, (self.pool[0],))

    def test_watched_or_not_interested_does_not_advance(self):
        for u in self.players:
            self.game = vote_on_current(self.game, u, WATCHED)
        self.assertNotIn(self.pool[0], self.game.candidates)
        self.assertEqual(self.game.current, self.pool[1])

    def test_mixed_votes_does_not_advance(self):
        self.game = vote_on_current(self.game, "a", INTERESTED)
        self.game = vote_on_current(self.game, "b", INTERESTED)
        self.game = vote_on_current(self.game, "c", NOT_INTERESTED)
        self.assertNotIn(self.pool[0], self.game.candidates)
        self.assertEqual(self.game.current, self.pool[1])

    def test_changing_a_vote_flips_the_result(self):
        self.game = vote_on_current(self.game, "a", INTERESTED)
        self.game = vote_on_current(self.game, "b", NOT_INTERESTED)
        self.game = vote_on_current(self.game, "b", INTERESTED)
        self.game = vote_on_current(self.game, "c", INTERESTED)
        self.assertIn(self.pool[0], self.game.candidates)

    def test_stale_vote_is_noop(self):
        g = new_game(["a", "b"], [10, 11, 12])
        for u in "ab":
            g = mark_ready(g, u)
        g = vote(g, "a", 10, INTERESTED)
        g = vote(g, "b", 10, INTERESTED)  # 10 advances, current == 11
        self.assertEqual(g.current, 11)
        self.assertEqual(g.candidates, (10,))
        g2 = vote(g, "a", 10, INTERESTED)  # stale vote for the decided movie 10
        self.assertEqual(g2, g)
        self.assertNotIn("a", g2.votes.get(11, {}))

    def test_votes_from_non_players_do_not_block_completion(self):
        g = new_game(["a", "b"], [10, 11])
        for u in "ab":
            g = mark_ready(g, u)
        g = replace(g, votes={10: {"a": INTERESTED, "x": WATCHED}})
        g = vote(g, "b", 10, INTERESTED)
        self.assertIn(10, g.candidates)
        self.assertEqual(g.current, 11)


class AdvanceTest(unittest.TestCase):
    def setUp(self):
        self.players, self.pool = players_and_pool()
        self.game = new_game(self.players, self.pool)
        for u in "abc":
            self.game = mark_ready(self.game, u)

    def test_force_advance_skips_current(self):
        g = self.game
        g = vote_on_current(g, "a", INTERESTED)  # a interested, b and c pending
        g2 = advance(g)  # host skips 0
        self.assertEqual(g2.current, self.pool[1])
        self.assertEqual(g2.candidates, ())  # 0 was not added to finalists
        self.assertEqual(g2.status, PLAYING)

    def test_force_advance_noop_outside_playing(self):
        ready_game = new_game(self.players, self.pool)
        self.assertEqual(advance(ready_game).status, READY)
        g = self._advance_to_final()
        self.assertEqual(advance(g).status, FINAL_ROUND)

    def test_force_advance_exhausts_to_terminal(self):
        g = new_game(["a"], [10])
        g = mark_ready(g, "a")
        g2 = advance(g)  # no next movie
        self.assertEqual(g2.status, FINISHED)
        self.assertIsNone(g2.winner)

    def test_force_advance_exhausts_to_final_round_with_finalists(self):
        g = new_game(["a"], [10, 11])
        g = mark_ready(g, "a")
        g = vote_on_current(g, "a", INTERESTED)  # 10 advances, current == 11
        g = advance(g)  # skip 11, exhausted, one finalist
        self.assertEqual(g.status, FINAL_ROUND)
        self.assertEqual(g.candidates, (10,))
        self.assertIsNone(g.current)

    def _advance_to_final(self):
        for _ in range(FINALIST_COUNT):
            self.game = unanimous_interested(self.game)
        return self.game


class FinalRoundTest(unittest.TestCase):
    def setUp(self):
        self.players, self.pool = players_and_pool()
        self.game = new_game(self.players, self.pool)
        for u in "abc":
            self.game = mark_ready(self.game, u)

    def _advance(self, n):
        for _ in range(n):
            self.game = unanimous_interested(self.game)
        return self.game

    def test_final_round_reaches_10_finalists(self):
        g = self._advance(FINALIST_COUNT - 1)
        self.assertEqual(g.status, PLAYING)
        self.assertEqual(len(g.candidates), FINALIST_COUNT - 1)
        g = self._advance(1)
        self.assertEqual(g.status, FINAL_ROUND)
        self.assertEqual(len(g.candidates), FINALIST_COUNT)
        self.assertIsNone(g.current)

    def test_pick_outside_final_round_noop(self):
        g = self.game  # PLAYING, no finalists yet
        g2 = pick(g, "a", 0)
        self.assertEqual(g2, g)
        self.assertEqual(g2.status, g.status)
        self.assertIsNone(g2.winner)

    def test_pick_restricted_to_finalists(self):
        g = self._advance(FINALIST_COUNT)
        g2 = pick(g, "a", 999)
        self.assertEqual(g2.status, FINAL_ROUND)
        self.assertIsNone(g2.winner)

    def test_pick_completes_to_winner(self):
        g = self._advance(FINALIST_COUNT)
        g = pick(g, "a", 0)
        g = pick(g, "b", 0)
        g = pick(g, "c", 0)
        self.assertEqual(g.status, FINISHED)
        self.assertEqual(g.winner, 0)

    def test_winner_is_most_picks(self):
        g = self._advance(FINALIST_COUNT)
        g = pick(g, "a", 1)
        g = pick(g, "b", 1)
        g = pick(g, "c", 2)
        self.assertEqual(g.winner, 1)

    def test_winner_tie_breaks_to_lower_id(self):
        g = self._advance(FINALIST_COUNT)
        g = pick(g, "a", 2)
        g = pick(g, "b", 4)
        g = pick(g, "c", 6)
        self.assertEqual(g.winner, 2)

    def test_one_pick_per_user_overwrites(self):
        g = make_final_round(["a", "b", "c"], [10, 11, 12])
        g = pick(g, "a", 10)
        g = pick(g, "a", 11)  # a re-picks; the first pick is discarded
        g = pick(g, "b", 12)
        g = pick(g, "c", 12)
        self.assertEqual(g.picks, {"a": 11, "b": 12, "c": 12})
        self.assertEqual(g.status, FINISHED)
        self.assertEqual(g.winner, 12)

    def test_picks_from_non_players_do_not_block_completion(self):
        g = make_final_round(["a", "b"], [10, 11])
        g = pick(g, "a", 10)
        g = replace(g, picks={"a": 10, "x": 11})
        g = pick(g, "b", 10)
        self.assertEqual(g.status, FINISHED)
        self.assertEqual(g.winner, 10)
        self.assertEqual(g.picks, {"a": 10, "b": 10})


class PoolExhaustionTest(unittest.TestCase):
    def test_exhaustion_before_finalists_ends_game(self):
        g = new_game(["a"], [10, 11])
        g = mark_ready(g, "a")
        g = vote_on_current(g, "a", WATCHED)  # 10 decided, not advanced
        g = vote_on_current(g, "a", WATCHED)  # 11 decided, not advanced, exhausted
        self.assertEqual(g.status, FINISHED)
        self.assertIsNone(g.winner)
        self.assertEqual(g.candidates, ())

    def test_exhaustion_with_finalists_goes_to_final_round(self):
        g = new_game(["a"], [10, 11])
        g = mark_ready(g, "a")
        g = vote_on_current(g, "a", INTERESTED)  # 10 advances, current == 11
        g = vote_on_current(g, "a", WATCHED)  # 11 decided, exhausted, one finalist
        self.assertEqual(g.status, FINAL_ROUND)
        self.assertEqual(g.candidates, (10,))
        self.assertIsNone(g.current)
        self.assertIsNone(g.winner)


class ImmutabilityTest(unittest.TestCase):
    def test_functions_return_new_object_and_preserve_original(self):
        players, pool = players_and_pool()
        original = new_game(players, pool)
        g = mark_ready(original, "a")
        self.assertIsNot(g, original)
        self.assertEqual(original.ready, frozenset())
        self.assertIn("a", g.ready)

    def test_noop_returns_same_object_and_preserve_original(self):
        players, pool = players_and_pool()
        original = new_game(players, pool)
        h = vote(original, "a", 0, INTERESTED)
        self.assertIs(h, original)
        self.assertEqual(original.status, READY)


class DeduplicationTest(unittest.TestCase):
    def test_new_game_deduplicates_players_and_pool(self):
        game = new_game(["a", "a", "b"], [10, 10, 11])
        self.assertEqual(game.players, frozenset({"a", "b"}))
        self.assertEqual(game.pool, (10, 11))


class InvalidInputTest(unittest.TestCase):
    def test_vote_rejects_unknown_choice(self):
        game = new_game(["a"], [10])
        game = mark_ready(game, "a")
        with self.assertRaises(InvalidChoiceError):
            vote(game, "a", 10, "maybe")

    def test_unknown_player_cannot_ready_vote_or_pick(self):
        game = new_game(["a"], [10])
        self.assertIs(mark_ready(game, "x"), game)
        self.assertIs(vote(game, "x", 10, INTERESTED), game)
        final = make_final_round(["a"], [10])
        self.assertIs(pick(final, "x", 10), final)

    def test_repeated_ready_and_same_vote_are_noops(self):
        game = new_game(["a", "b"], [10])
        game = mark_ready(game, "a")
        self.assertIs(mark_ready(game, "a"), game)
        game = mark_ready(game, "b")
        game = vote(game, "a", 10, INTERESTED)
        self.assertIs(vote(game, "a", 10, INTERESTED), game)


class EmptyPoolTest(unittest.TestCase):
    def test_ready_with_empty_pool_finishes(self):
        game = new_game(["a"], [])
        game = mark_ready(game, "a")
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.current)
        self.assertIsNone(game.winner)

    def test_reconcile_starting_with_empty_pool_finishes(self):
        game = Game(status=READY, players=frozenset({"a"}), ready=frozenset({"a"}), pool=(), pool_index=0)
        game = reconcile(game)
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)


class ReconcileTest(unittest.TestCase):
    def test_leaver_removal_can_start_the_game(self):
        game = new_game(["a", "b"], [10])
        game = mark_ready(game, "a")
        game = replace(game, players=frozenset({"a"}), ready=frozenset({"a", "b"}))
        game = reconcile(game)
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.current, 10)
        self.assertEqual(game.ready, frozenset({"a"}))

    def test_leaver_removal_can_complete_the_current_movie(self):
        game = new_game(["a", "b"], [10, 11])
        game = mark_ready(game, "a")
        game = mark_ready(game, "b")
        game = vote(game, "a", 10, INTERESTED)
        game = replace(game, players=frozenset({"a"}), ready=frozenset({"a", "b"}))
        game = reconcile(game)
        self.assertEqual(game.candidates, (10,))
        self.assertEqual(game.current, 11)

    def test_final_round_resolves_when_remaining_players_have_picked(self):
        game = make_final_round(["a", "b"], [10, 11])
        game = pick(game, "a", 10)
        game = replace(game, players=frozenset({"a"}))
        game = reconcile(game)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.winner, 10)

    def test_stale_ready_votes_and_picks_are_pruned(self):
        game = make_final_round(["a", "b", "c"], [10, 11])
        game = replace(game, picks={"a": 10, "x": 11}, ready=frozenset({"a", "x"}))
        game = reconcile(game)
        self.assertEqual(game.ready, frozenset({"a"}))
        self.assertEqual(game.picks, {"a": 10})

        playing = Game(
            status=PLAYING,
            players=frozenset({"a", "b"}),
            ready=frozenset({"a", "x"}),
            pool=(10, 11),
            pool_index=0,
            current=10,
            votes={10: {"a": INTERESTED, "x": WATCHED}},
            candidates=(),
        )
        playing = reconcile(playing)
        self.assertEqual(playing.ready, frozenset({"a"}))
        self.assertEqual(playing.votes[10], {"a": INTERESTED})
        self.assertEqual(playing.status, PLAYING)

    def test_playing_without_current_finishes(self):
        game = Game(
            status=PLAYING,
            players=frozenset({"a"}),
            ready=frozenset({"a"}),
            pool=(),
            pool_index=0,
            current=None,
        )
        game = reconcile(game)
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_playing_without_current_keeps_finalists(self):
        game = Game(
            status=PLAYING,
            players=frozenset({"a"}),
            ready=frozenset({"a"}),
            pool=(10,),
            pool_index=0,
            current=None,
            candidates=(10,),
        )
        game = reconcile(game)
        self.assertEqual(game.status, FINAL_ROUND)
        self.assertEqual(game.candidates, (10,))

    def test_no_players_finishes(self):
        game = Game(status=READY, players=frozenset(), ready=frozenset(), pool=(10,), pool_index=0)
        game = reconcile(game)
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_finished_game_is_unchanged(self):
        game = Game(
            status=FINISHED,
            players=frozenset({"a"}),
            ready=frozenset({"a"}),
            pool=(10,),
            pool_index=0,
            winner=10,
        )
        self.assertIs(reconcile(game), game)


class FinalizeTest(unittest.TestCase):
    def test_no_picks_finishes_without_winner(self):
        game = make_final_round(["a", "b"], [10, 11])
        game = finalize(game)
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_partial_picks_still_produce_winner(self):
        game = make_final_round(["a", "b", "c"], [10, 11])
        game = pick(game, "a", 10)
        game = finalize(game)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.winner, 10)

    def test_finalize_outside_final_round_is_noop(self):
        game = new_game(["a"], [10])
        self.assertIs(finalize(game), game)


class EndTest(unittest.TestCase):
    def test_end_from_ready(self):
        game = end(new_game(["a"], [10]))
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.current)
        self.assertIsNone(game.winner)

    def test_end_from_playing(self):
        game = new_game(["a"], [10])
        game = mark_ready(game, "a")
        game = end(game)
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.current)
        self.assertIsNone(game.winner)

    def test_end_from_final_round_clears_winner(self):
        game = make_final_round(["a"], [10])
        game = end(game)
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_end_is_idempotent(self):
        game = end(new_game(["a"], [10]))
        self.assertIs(end(game), game)


if __name__ == "__main__":
    unittest.main()
