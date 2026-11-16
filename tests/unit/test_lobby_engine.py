import unittest
from collections.abc import Iterable
from dataclasses import replace

from app.domain.lobby.engine import (
    FINAL_ROUND,
    FINALIST_COUNT,
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
    next_round,
    pick,
    reconcile,
    start,
    unready,
    vote,
)
from app.domain.lobby.exceptions import InvalidChoiceError

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


def reveal_round(game: Game, choice: str = INTERESTED) -> Game:
    return cast_votes(game, sorted(game.players), choice)


def play_rounds(game: Game, count: int, choice: str = INTERESTED) -> Game:
    for _ in range(count):
        game = reveal_round(game, choice)
        if game.status == PLAYING:
            game = next_round(game)
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
        self.assertFalse(game.revealed)
        self.assertFalse(game.picks_revealed)


class ReadyTest(unittest.TestCase):
    def test_ready_records_player_and_is_idempotent(self) -> None:
        game = mark_ready(new_game(PLAYERS, POOL), "a")
        self.assertEqual(game.status, READY)
        self.assertEqual(game.ready, frozenset({"a"}))
        self.assertIs(mark_ready(game, "a"), game)

    def test_everyone_ready_does_not_start_the_game(self) -> None:
        game = ready_all(new_game(PLAYERS, POOL))
        self.assertEqual(game.status, READY)
        self.assertEqual(game.ready, frozenset(PLAYERS))
        self.assertIsNone(game.current)

    def test_unready_removes_player_and_is_idempotent(self) -> None:
        game = ready_all(new_game(PLAYERS, POOL))
        game = unready(game, "a")
        self.assertEqual(game.ready, frozenset({"b", "c"}))
        self.assertIs(unready(game, "a"), game)
        self.assertIs(unready(game, "x"), game)

    def test_unknown_player_and_non_ready_state_are_noops(self) -> None:
        game = new_game(PLAYERS, POOL)
        self.assertIs(mark_ready(game, "x"), game)
        started = start(game)
        self.assertIs(mark_ready(started, "a"), started)
        self.assertIs(unready(started, "a"), started)


class StartTest(unittest.TestCase):
    def test_start_uses_all_players_by_default(self) -> None:
        game = start(ready_all(new_game(PLAYERS, POOL)))
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.players, frozenset(PLAYERS))
        self.assertEqual(game.ready, frozenset(PLAYERS))
        self.assertEqual(game.current, POOL[0])
        self.assertFalse(game.revealed)

    def test_start_can_select_ready_players(self) -> None:
        game = start(new_game(PLAYERS, POOL), ["a", "c"])
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.players, frozenset({"a", "c"}))
        self.assertEqual(game.ready, frozenset({"a", "c"}))

    def test_start_ignores_unknown_players(self) -> None:
        game = start(new_game(PLAYERS, POOL), ["a", "x"])
        self.assertEqual(game.players, frozenset({"a"}))

    def test_start_with_no_players_finishes(self) -> None:
        game = start(new_game(PLAYERS, POOL), [])
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.current)

    def test_start_with_empty_pool_finishes(self) -> None:
        game = start(new_game(["a"], []))
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.current)
        self.assertIsNone(game.winner)

    def test_start_outside_ready_is_noop(self) -> None:
        playing = start(new_game(PLAYERS, POOL))
        self.assertIs(start(playing), playing)


class VoteTest(unittest.TestCase):
    def test_vote_records_choice_and_ignores_unknown_players(self) -> None:
        game = start(new_game(PLAYERS, POOL))
        game = vote(game, "a", game.current, INTERESTED)
        self.assertEqual(game.votes[POOL[0]], {"a": INTERESTED})
        self.assertFalse(game.revealed)
        self.assertIs(vote(game, "x", game.current, INTERESTED), game)

    def test_same_vote_is_noop_and_changed_vote_overwrites(self) -> None:
        game = start(new_game(PLAYERS, POOL))
        game = vote(game, "a", POOL[0], INTERESTED)
        self.assertIs(vote(game, "a", POOL[0], INTERESTED), game)
        game = vote(game, "a", POOL[0], WATCHED)
        self.assertEqual(game.votes[POOL[0]], {"a": WATCHED})

    def test_stale_vote_is_noop(self) -> None:
        game = start(new_game(["a", "b"], [10, 11, 12]))
        game = reveal_round(game)
        game = next_round(game)
        self.assertEqual(game.current, 11)
        self.assertIs(vote(game, "a", 10, INTERESTED), game)
        self.assertNotIn("a", game.votes.get(11, {}))

    def test_all_votes_reveal_without_advancing(self) -> None:
        game = start(new_game(PLAYERS, POOL))
        game = reveal_round(game)
        self.assertEqual(game.status, PLAYING)
        self.assertTrue(game.revealed)
        self.assertEqual(game.current, POOL[0])
        self.assertEqual(game.pool_index, 0)
        self.assertEqual(game.candidates, (POOL[0],))

    def test_only_unanimous_interested_adds_a_finalist(self) -> None:
        cases = (
            (WATCHED, WATCHED, WATCHED),
            (NOT_INTERESTED, NOT_INTERESTED, NOT_INTERESTED),
            (INTERESTED, INTERESTED, NOT_INTERESTED),
        )
        for choices in cases:
            with self.subTest(choices=choices):
                game = start(new_game(PLAYERS, POOL))
                for user, choice in zip(sorted(PLAYERS), choices, strict=True):
                    game = vote(game, user, game.current, choice)
                self.assertTrue(game.revealed)
                self.assertEqual(game.candidates, ())
                self.assertEqual(game.current, POOL[0])

    def test_non_player_votes_do_not_block_completion(self) -> None:
        game = start(new_game(["a", "b"], [10, 11]))
        game = replace(game, votes={10: {"a": INTERESTED, "x": WATCHED}})
        game = vote(game, "b", 10, INTERESTED)
        self.assertTrue(game.revealed)
        self.assertEqual(game.candidates, (10,))

    def test_invalid_choice_raises(self) -> None:
        game = start(new_game(["a"], [10]))
        with self.assertRaises(InvalidChoiceError):
            vote(game, "a", 10, "maybe")

    def test_vote_after_reveal_is_noop(self) -> None:
        game = reveal_round(start(new_game(PLAYERS, POOL)))
        self.assertIs(vote(game, "a", POOL[0], WATCHED), game)


class AdvanceTest(unittest.TestCase):
    def test_advance_skips_current_without_adding_a_finalist(self) -> None:
        game = reveal_round(start(new_game(PLAYERS, POOL)), WATCHED)
        game = next_round(game)
        game = advance(game)
        self.assertEqual(game.current, POOL[2])
        self.assertEqual(game.candidates, ())
        self.assertEqual(game.status, PLAYING)
        self.assertFalse(game.revealed)

    def test_advance_is_unavailable_after_reveal(self) -> None:
        game = reveal_round(start(new_game(PLAYERS, POOL)))
        self.assertIs(advance(game), game)

    def test_advance_outside_playing_is_noop(self) -> None:
        ready = new_game(PLAYERS, POOL)
        self.assertIs(advance(ready), ready)
        final = final_round()
        self.assertIs(advance(final), final)

    def test_advance_exhaustion_finishes_or_enters_final_round(self) -> None:
        no_finalists = start(new_game(["a"], [10]))
        ended = advance(no_finalists)
        self.assertEqual(ended.status, FINISHED)
        self.assertIsNone(ended.winner)

        with_finalists = reveal_round(start(new_game(["a"], [10, 11])))
        with_finalists = next_round(with_finalists)
        with_finalists = advance(with_finalists)
        self.assertEqual(with_finalists.status, FINAL_ROUND)
        self.assertEqual(with_finalists.candidates, (10,))


class NextRoundTest(unittest.TestCase):
    def test_next_round_requires_a_reveal(self) -> None:
        game = start(new_game(PLAYERS, POOL))
        self.assertIs(next_round(game), game)

    def test_next_round_moves_to_the_next_film(self) -> None:
        game = reveal_round(start(new_game(PLAYERS, POOL)))
        game = next_round(game)
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.pool_index, 1)
        self.assertEqual(game.current, POOL[1])
        self.assertFalse(game.revealed)

    def test_ten_finalists_start_the_final_round(self) -> None:
        game = start(new_game(PLAYERS, POOL))
        game = play_rounds(game, FINALIST_COUNT - 1)
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(len(game.candidates), FINALIST_COUNT - 1)
        game = reveal_round(game)
        self.assertEqual(len(game.candidates), FINALIST_COUNT)
        game = next_round(game)
        self.assertEqual(game.status, FINAL_ROUND)
        self.assertEqual(game.current, None)

    def test_pool_exhaustion_after_reveal_enters_final_or_finishes(self) -> None:
        with_finalists = reveal_round(start(new_game(["a"], [10, 11])))
        with_finalists = next_round(with_finalists)
        with_finalists = reveal_round(with_finalists, WATCHED)
        with_finalists = next_round(with_finalists)
        self.assertEqual(with_finalists.status, FINAL_ROUND)
        self.assertEqual(with_finalists.candidates, (10,))

        no_finalists = reveal_round(start(new_game(["a"], [10])), WATCHED)
        no_finalists = next_round(no_finalists)
        self.assertEqual(no_finalists.status, FINISHED)
        self.assertIsNone(no_finalists.winner)


class FinalRoundTest(unittest.TestCase):
    def test_pick_requires_final_round_and_a_finalist(self) -> None:
        playing = start(new_game(PLAYERS, POOL))
        self.assertIs(pick(playing, "a", POOL[0]), playing)
        final = final_round()
        self.assertIs(pick(final, "a", 999), final)
        self.assertIs(pick(final, "x", 10), final)

    def test_all_picks_reveal_but_do_not_finish(self) -> None:
        game = final_round(("a", "b", "c"), (10, 11, 12))
        game = pick(game, "a", 11)
        game = pick(game, "b", 12)
        self.assertFalse(game.picks_revealed)
        game = pick(game, "c", 12)
        self.assertEqual(game.status, FINAL_ROUND)
        self.assertTrue(game.picks_revealed)
        self.assertIsNone(game.winner)

    def test_picks_overwrite_before_reveal(self) -> None:
        game = final_round(("a", "b", "c"), (10, 11, 12))
        game = pick(game, "a", 10)
        game = pick(game, "a", 11)
        self.assertEqual(game.picks, {"a": 11})

    def test_pick_after_reveal_is_noop(self) -> None:
        game = pick(final_round(("a",), (10, 11)), "a", 10)
        self.assertTrue(game.picks_revealed)
        self.assertIs(pick(game, "a", 11), game)


class FinalizeEndTest(unittest.TestCase):
    def test_finalize_without_picks_finishes_without_winner(self) -> None:
        game = finalize(final_round(("a", "b"), (10, 11)))
        self.assertEqual(game.status, FINISHED)
        self.assertIsNone(game.winner)
        self.assertTrue(game.picks_revealed)

    def test_finalize_partial_picks_resolves_winner(self) -> None:
        game = pick(final_round(("a", "b", "c"), (10, 11)), "a", 10)
        game = finalize(game)
        self.assertEqual(game.status, FINISHED)
        self.assertEqual(game.winner, 10)

    def test_winner_is_most_picks_and_ties_break_to_lowest_id(self) -> None:
        game = final_round(("a", "b", "c"), (10, 11, 12))
        game = pick(game, "a", 11)
        game = pick(game, "b", 12)
        game = pick(game, "c", 12)
        self.assertEqual(finalize(game).winner, 12)

        tie = final_round(("a", "b", "c"), (10, 11, 12))
        tie = pick(tie, "a", 12)
        tie = pick(tie, "b", 10)
        tie = pick(tie, "c", 11)
        self.assertEqual(finalize(tie).winner, 10)

    def test_non_player_picks_do_not_block_completion(self) -> None:
        game = final_round(("a", "b"), (10, 11))
        game = pick(game, "a", 10)
        game = replace(game, picks={"a": 10, "x": 11})
        game = pick(game, "b", 10)
        self.assertTrue(game.picks_revealed)
        self.assertEqual(finalize(game).winner, 10)
        self.assertEqual(game.picks, {"a": 10, "b": 10})

    def test_finalize_outside_final_round_is_noop(self) -> None:
        game = new_game(["a"], [10])
        self.assertIs(finalize(game), game)

    def test_end_clears_active_state_and_is_idempotent(self) -> None:
        games = (
            new_game(["a"], [10]),
            reveal_round(start(new_game(["a"], [10]))),
            replace(final_round(("a",), (10,)), winner=10),
        )
        for game in games:
            with self.subTest(status=game.status):
                ended = end(game)
                self.assertEqual(ended.status, FINISHED)
                self.assertIsNone(ended.current)
                self.assertIsNone(ended.winner)
                self.assertFalse(ended.revealed)
                self.assertFalse(ended.picks_revealed)
                self.assertIs(end(ended), ended)


class ReconcileTest(unittest.TestCase):
    def test_leaver_during_ready_does_not_start_the_game(self) -> None:
        game = ready_all(new_game(["a", "b"], [10]))
        game = replace(game, players=frozenset({"a"}))
        game = reconcile(game)
        self.assertEqual(game.status, READY)
        self.assertEqual(game.ready, frozenset({"a"}))

    def test_leaver_removal_can_complete_the_current_movie(self) -> None:
        game = ready_all(new_game(["a", "b"], [10, 11]))
        game = start(game)
        game = vote(game, "a", 10, INTERESTED)
        game = replace(game, players=frozenset({"a"}))
        game = reconcile(game)
        self.assertTrue(game.revealed)
        self.assertEqual(game.candidates, (10,))
        self.assertEqual(game.current, 10)

    def test_leaver_removal_can_reveal_the_final_round(self) -> None:
        game = pick(final_round(("a", "b"), (10, 11)), "a", 10)
        game = replace(game, players=frozenset({"a"}))
        game = reconcile(game)
        self.assertEqual(game.status, FINAL_ROUND)
        self.assertTrue(game.picks_revealed)
        self.assertIsNone(game.winner)

    def test_reconcile_prunes_stale_ready_votes_and_picks(self) -> None:
        final = replace(
            final_round(("a", "b", "c"), (10, 11)),
            picks={"a": 10, "b": 99, "x": 11},
            ready=frozenset({"a", "x"}),
        )
        final = reconcile(final)
        self.assertEqual(final.ready, frozenset({"a"}))
        self.assertEqual(final.picks, {"a": 10})

        playing = replace(
            start(new_game(["a", "b"], [10, 11])),
            ready=frozenset({"a", "x"}),
            votes={10: {"a": INTERESTED, "x": WATCHED}},
        )
        playing = reconcile(playing)
        self.assertEqual(playing.ready, frozenset({"a"}))
        self.assertEqual(playing.votes[10], {"a": INTERESTED})
        self.assertEqual(playing.status, PLAYING)
        self.assertFalse(playing.revealed)

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

    def test_ready_empty_pool_does_not_finish_until_started(self) -> None:
        game = reconcile(Game(status=READY, players=frozenset({"a"}), ready=frozenset({"a"}), pool=(), pool_index=0))
        self.assertEqual(game.status, READY)
        self.assertEqual(start(game).status, FINISHED)

    def test_finished_game_is_unchanged(self) -> None:
        game = Game(
            status=FINISHED,
            players=frozenset({"a"}),
            ready=frozenset({"a"}),
            pool=(10,),
            pool_index=0,
            winner=10,
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
        playing = start(ready)
        revealed = reveal_round(start(new_game(PLAYERS, POOL)))
        finished = end(ready)
        cases = (
            ("unknown ready", ready, mark_ready(ready, "x")),
            ("vote in ready", ready, vote(ready, "a", 0, INTERESTED)),
            ("pick in playing", playing, pick(playing, "a", 0)),
            ("next round in playing", playing, next_round(playing)),
            ("advance in ready", ready, advance(ready)),
            ("finalize in playing", playing, finalize(playing)),
            ("end finished", finished, end(finished)),
        )
        for name, original, result in cases:
            with self.subTest(name):
                self.assertIs(result, original)
        self.assertTrue(revealed.revealed)


if __name__ == "__main__":
    unittest.main()
