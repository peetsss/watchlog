import unittest
from collections.abc import Iterable
from dataclasses import replace

from lobby.engine import (
    FINALIST_COUNT,
    FINAL_ROUND,
    FINISHED,
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

PLAYERS = ("a", "b", "c")
POOL = tuple(range(10))


def ready_all(game: Game) -> Game:
    for user in sorted(game.players):
        game = mark_ready(game, user)
    return game


def cast_votes(game: Game, users: Iterable[str], choice: str = INTERESTED) -> Game:
    for user in users:
        if game.current is None:
            raise AssertionError("expected a current movie")
        game = vote(game, user, game.current, choice)
    return game


def play_rounds(game: Game, count: int) -> Game:
    for _ in range(count):
        game = cast_votes(game, sorted(game.players))
    return game


def final_round(players: Iterable[str] = ("a", "b"), candidates: Iterable[int] = (10, 11)) -> Game:
    player_set = frozenset(players)
    return Game(
        status=FINAL_ROUND,
        players=player_set,
        ready=player_set,
        pool=(),
        pool_index=0,
        current=None,
        candidates=tuple(candidates),
    )


class NewGameTest(unittest.TestCase):
    def test_initial_state_and_deduplication(self) -> None:
        game = new_game(["a", "a", "b"], [10, 10, 11])
        self.assertEqual(game.status, READY)
        self.assertEqual(game.players, frozenset({"a", "b"}))
        self.assertEqual(game.ready, frozenset())
        self.assertEqual(game.pool, (10, 11))
        self.assertEqual(game.pool_index, 0)
        self.assertIsNone(game.current)
        self.assertEqual(game.votes, {})
        self.assertEqual(game.picks, {})
        self.assertEqual(game.candidates, ())
        self.assertIsNone(game.winner)


class ReadyTest(unittest.TestCase):
    def test_ready_records_player_and_is_idempotent(self) -> None:
        game = mark_ready(new_game(PLAYERS, POOL), "a")
        self.assertEqual(game.status, READY)
        self.assertEqual(game.ready, frozenset({"a"}))
        self.assertIs(mark_ready(game, "a"), game)

    def test_last_ready_starts_game(self) -> None:
        game = ready_all(new_game(PLAYERS, POOL))
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.current, POOL[0])

    def test_unknown_player_and_non_ready_state_are_noops(self) -> None:
        game = new_game(PLAYERS, POOL)
        self.assertIs(mark_ready(game, "x"), game)
        started = ready_all(game)
        self.assertIs(mark_ready(started, "a"), started)

    def test_empty_pool_finishes_when_everyone_is_ready(self) -> None:
        game = mark_ready(new_game(["a"], []), "a")
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.current)
        self.assertIsNone(game.winner)


class VoteTest(unittest.TestCase):
    def test_vote_records_choice_and_ignores_unknown_players(self) -> None:
        game = ready_all(new_game(PLAYERS, POOL))
        game = vote(game, "a", game.current, INTERESTED)
        self.assertEqual(game.votes[POOL[0]], {"a": INTERESTED})
        self.assertIs(vote(game, "x", game.current, INTERESTED), game)

    def test_same_vote_is_noop_and_changed_vote_overwrites(self) -> None:
        game = cast_votes(ready_all(new_game(PLAYERS, POOL)), ["a"])
        self.assertIs(vote(game, "a", POOL[0], INTERESTED), game)
        game = vote(game, "a", POOL[0], WATCHED)
        self.assertEqual(game.votes[POOL[0]], {"a": WATCHED})

    def test_stale_vote_is_noop(self) -> None:
        game = ready_all(new_game(["a", "b"], [10, 11, 12]))
        game = cast_votes(game, ["a", "b"])
        self.assertEqual(game.current, 11)
        self.assertEqual(game.candidates, (10,))
        self.assertIs(vote(game, "a", 10, INTERESTED), game)
        self.assertNotIn("a", game.votes.get(11, {}))

    def test_only_unanimous_interested_advances(self) -> None:
        cases = (
            (WATCHED, WATCHED, WATCHED),
            (NOT_INTERESTED, NOT_INTERESTED, NOT_INTERESTED),
            (INTERESTED, INTERESTED, NOT_INTERESTED),
        )
        for choices in cases:
            with self.subTest(choices=choices):
                game = ready_all(new_game(PLAYERS, POOL))
                for user, choice in zip(sorted(PLAYERS), choices, strict=True):
                    game = vote(game, user, game.current, choice)
                self.assertEqual(game.status, PLAYING)
                self.assertEqual(game.candidates, ())
                self.assertEqual(game.current, POOL[1])

        game = cast_votes(ready_all(new_game(PLAYERS, POOL)), sorted(PLAYERS))
        self.assertEqual(game.candidates, (POOL[0],))
        self.assertEqual(game.current, POOL[1])

    def test_non_player_votes_do_not_block_completion(self) -> None:
        game = ready_all(new_game(["a", "b"], [10, 11]))
        game = replace(game, votes={10: {"a": INTERESTED, "x": WATCHED}})
        game = vote(game, "b", 10, INTERESTED)
        self.assertEqual(game.candidates, (10,))
        self.assertEqual(game.current, 11)

    def test_invalid_choice_raises(self) -> None:
        game = ready_all(new_game(["a"], [10]))
        with self.assertRaises(InvalidChoiceError):
            vote(game, "a", 10, "maybe")

    def test_pool_exhaustion_after_a_vote(self) -> None:
        ended = ready_all(new_game(["a"], [10]))
        ended = vote(ended, "a", 10, WATCHED)
        self.assertEqual(ended.status, FINISHED)
        self.assertIsNone(ended.winner)

        final = ready_all(new_game(["a"], [10, 11]))
        final = vote(final, "a", 10, INTERESTED)
        final = vote(final, "a", 11, WATCHED)
        self.assertEqual(final.status, FINAL_ROUND)
        self.assertEqual(final.candidates, (10,))
        self.assertIsNone(final.current)


class AdvanceTest(unittest.TestCase):
    def test_advance_skips_current_without_adding_a_finalist(self) -> None:
        game = cast_votes(ready_all(new_game(PLAYERS, POOL)), ["a"])
        game = advance(game)
        self.assertEqual(game.current, POOL[1])
        self.assertEqual(game.candidates, ())
        self.assertEqual(game.status, PLAYING)

    def test_advance_outside_playing_is_noop(self) -> None:
        ready = new_game(PLAYERS, POOL)
        self.assertIs(advance(ready), ready)
        final = final_round()
        self.assertIs(advance(final), final)

    def test_advance_exhaustion_finishes_or_enters_final_round(self) -> None:
        no_finalists = ready_all(new_game(["a"], [10]))
        ended = advance(no_finalists)
        self.assertEqual(ended.status, FINISHED)
        self.assertIsNone(ended.winner)

        with_finalists = ready_all(new_game(["a"], [10, 11]))
        with_finalists = cast_votes(with_finalists, ["a"])
        with_finalists = advance(with_finalists)
        self.assertEqual(with_finalists.status, FINAL_ROUND)
        self.assertEqual(with_finalists.candidates, (10,))
        self.assertIsNone(with_finalists.current)


class FinalRoundTest(unittest.TestCase):
    def test_ten_finalists_start_final_round(self) -> None:
        game = ready_all(new_game(PLAYERS, POOL))
        game = play_rounds(game, FINALIST_COUNT - 1)
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(len(game.candidates), FINALIST_COUNT - 1)
        game = cast_votes(game, sorted(PLAYERS))
        self.assertEqual(game.status, FINAL_ROUND)
        self.assertEqual(len(game.candidates), FINALIST_COUNT)
        self.assertIsNone(game.current)

    def test_pick_requires_final_round_and_a_finalist(self) -> None:
        playing = ready_all(new_game(PLAYERS, POOL))
        self.assertIs(pick(playing, "a", POOL[0]), playing)
        final = final_round()
        self.assertIs(pick(final, "a", 999), final)
        self.assertIs(pick(final, "x", 10), final)

    def test_picks_overwrite_and_completion_resolves_winner(self) -> None:
        game = final_round(("a", "b", "c"), (10, 11, 12))
        game = pick(game, "a", 10)
        game = pick(game, "a", 11)
        game = pick(game, "b", 12)
        game = pick(game, "c", 12)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.picks, {"a": 11, "b": 12, "c": 12})
        self.assertEqual(game.winner, 12)

    def test_winner_is_most_picks(self) -> None:
        game = final_round(("a", "b", "c"), (10, 11, 12))
        game = pick(game, "a", 11)
        game = pick(game, "b", 11)
        game = pick(game, "c", 12)
        self.assertEqual(game.winner, 11)

    def test_ties_break_to_lowest_movie_id(self) -> None:
        game = final_round(("a", "b", "c"), (10, 11, 12))
        game = pick(game, "a", 12)
        game = pick(game, "b", 10)
        game = pick(game, "c", 11)
        self.assertEqual(game.winner, 10)

    def test_non_player_picks_do_not_block_completion(self) -> None:
        game = final_round(("a", "b"), (10, 11))
        game = pick(game, "a", 10)
        game = replace(game, picks={"a": 10, "x": 11})
        game = pick(game, "b", 10)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.winner, 10)
        self.assertEqual(game.picks, {"a": 10, "b": 10})


class FinalizeEndTest(unittest.TestCase):
    def test_finalize_without_picks_finishes_without_winner(self) -> None:
        game = finalize(final_round(("a", "b"), (10, 11)))
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_finalize_partial_picks_resolves_winner(self) -> None:
        game = pick(final_round(("a", "b", "c"), (10, 11)), "a", 10)
        game = finalize(game)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.winner, 10)

    def test_finalize_outside_final_round_is_noop(self) -> None:
        game = new_game(["a"], [10])
        self.assertIs(finalize(game), game)

    def test_end_clears_active_state_and_is_idempotent(self) -> None:
        games = (
            new_game(["a"], [10]),
            ready_all(new_game(["a"], [10])),
            replace(final_round(("a",), (10,)), winner=10),
        )
        for game in games:
            with self.subTest(status=game.status):
                ended = end(game)
                self.assertEqual(ended.status, FINISHED)
                self.assertIsNone(ended.current)
                self.assertIsNone(ended.winner)
                self.assertIs(end(ended), ended)


class ReconcileTest(unittest.TestCase):
    def test_leaver_removal_can_start_the_game(self) -> None:
        game = mark_ready(new_game(["a", "b"], [10]), "a")
        game = replace(game, players=frozenset({"a"}), ready=frozenset({"a", "b"}))
        game = reconcile(game)
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.current, 10)
        self.assertEqual(game.ready, frozenset({"a"}))

    def test_leaver_removal_can_complete_the_current_movie(self) -> None:
        game = ready_all(new_game(["a", "b"], [10, 11]))
        game = vote(game, "a", 10, INTERESTED)
        game = replace(game, players=frozenset({"a"}))
        game = reconcile(game)
        self.assertEqual(game.candidates, (10,))
        self.assertEqual(game.current, 11)

    def test_leaver_removal_can_resolve_the_final_round(self) -> None:
        game = pick(final_round(("a", "b"), (10, 11)), "a", 10)
        game = replace(game, players=frozenset({"a"}))
        game = reconcile(game)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.winner, 10)

    def test_reconcile_prunes_stale_ready_votes_and_picks(self) -> None:
        final = replace(
            final_round(("a", "b", "c"), (10, 11)),
            picks={"a": 10, "b": 99, "x": 11},
            ready=frozenset({"a", "x"}),
        )
        final = reconcile(final)
        self.assertEqual(final.ready, frozenset({"a"}))
        self.assertEqual(final.picks, {"a": 10})

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

    def test_no_players_finishes(self) -> None:
        game = reconcile(Game(status=READY, players=frozenset(), ready=frozenset(), pool=(10,), pool_index=0))
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_playing_without_current_finishes_or_enters_final_round(self) -> None:
        cases = (((), FINISHED), ((10,), FINAL_ROUND))
        for candidates, status in cases:
            with self.subTest(candidates=candidates):
                game = Game(
                    status=PLAYING,
                    players=frozenset({"a"}),
                    ready=frozenset({"a"}),
                    pool=(10,) if candidates else (),
                    pool_index=0,
                    current=None,
                    candidates=candidates,
                )
                game = reconcile(game)
                self.assertEqual(game.status, status)
                self.assertEqual(game.candidates, candidates)

    def test_ready_empty_pool_finishes(self) -> None:
        game = reconcile(Game(status=READY, players=frozenset({"a"}), ready=frozenset({"a"}), pool=(), pool_index=0))
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)

    def test_finished_game_is_unchanged(self) -> None:
        game = Game(
            status=FINISHED, players=frozenset({"a"}), ready=frozenset({"a"}), pool=(10,), pool_index=0, winner=10
        )
        self.assertIs(reconcile(game), game)


class ImmutabilityTest(unittest.TestCase):
    def test_real_change_returns_new_game_and_preserves_original(self) -> None:
        original = new_game(PLAYERS, POOL)
        changed = mark_ready(original, "a")
        self.assertIsNot(changed, original)
        self.assertEqual(original.ready, frozenset())
        self.assertEqual(changed.ready, frozenset({"a"}))

    def test_noops_return_the_same_instance(self) -> None:
        ready = new_game(PLAYERS, POOL)
        playing = ready_all(ready)
        finished = end(ready)
        cases = (
            ("unknown ready", ready, mark_ready(ready, "x")),
            ("vote in ready", ready, vote(ready, "a", 0, INTERESTED)),
            ("pick in playing", playing, pick(playing, "a", 0)),
            ("advance in ready", ready, advance(ready)),
            ("finalize in playing", playing, finalize(playing)),
            ("end finished", finished, end(finished)),
        )
        for name, original, result in cases:
            with self.subTest(name):
                self.assertIs(result, original)


if __name__ == "__main__":
    unittest.main()
