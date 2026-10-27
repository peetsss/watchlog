from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from lobby.exceptions import InvalidChoiceError
from lobby.rules import (
    FINALIST_COUNT,
    FINAL_ROUND,
    FINISHED,
    INTERESTED,
    NOT_INTERESTED,
    PICK,
    PLAYING,
    READY,
    VOTE_CHOICES,
    WATCHED,
)

__all__ = [
    "FINALIST_COUNT",
    "FINAL_ROUND",
    "FINISHED",
    "INTERESTED",
    "NOT_INTERESTED",
    "PICK",
    "PLAYING",
    "READY",
    "VOTE_CHOICES",
    "WATCHED",
    "Game",
    "advance",
    "end",
    "finalize",
    "mark_ready",
    "new_game",
    "pick",
    "reconcile",
    "vote",
]


@dataclass(frozen=True, slots=True)
class Game:
    status: str
    players: frozenset[str]
    ready: frozenset[str]
    pool: tuple[int, ...]
    pool_index: int
    current: int | None = None
    votes: dict[int, dict[str, str]] = field(default_factory=dict)
    picks: dict[str, int] = field(default_factory=dict)
    candidates: tuple[int, ...] = ()
    winner: int | None = None


def new_game(players: Iterable[str], pool: Iterable[int]) -> Game:
    return Game(
        status=READY,
        players=frozenset(dict.fromkeys(players)),
        ready=frozenset(),
        pool=tuple(dict.fromkeys(pool)),
        pool_index=0,
        current=None,
        votes={},
        picks={},
        candidates=(),
        winner=None,
    )


def mark_ready(game: Game, user_id: str) -> Game:
    if game.status != READY or user_id not in game.players:
        return game
    ready = frozenset(user for user in game.ready if user in game.players)
    if user_id in ready:
        return game
    ready = ready | {user_id}
    if ready == game.players:
        return _start_playing(replace(game, ready=ready))
    return replace(game, ready=ready)


def vote(game: Game, user_id: str, movie_id: int, choice: str) -> Game:
    if choice not in VOTE_CHOICES:
        raise InvalidChoiceError(f"Unknown vote choice: {choice!r}")
    if game.status != PLAYING or game.current is None or user_id not in game.players:
        return game
    if movie_id != game.current:
        return game
    current_votes = game.votes.get(movie_id, {})
    if current_votes.get(user_id) == choice:
        return game
    votes = {**game.votes, movie_id: {**current_votes, user_id: choice}}
    player_votes = [user for user in votes[movie_id] if user in game.players]
    if len(player_votes) == len(game.players):
        return _decide_movie(game, movie_id, votes)
    return replace(game, votes=votes)


def advance(game: Game) -> Game:
    if game.status != PLAYING or game.current is None:
        return game
    return _next_movie(game, game.votes, game.candidates)


def pick(game: Game, user_id: str, movie_id: int) -> Game:
    if game.status != FINAL_ROUND or user_id not in game.players:
        return game
    if movie_id not in game.candidates:
        return game
    picks = {user: movie for user, movie in game.picks.items() if user in game.players}
    if picks.get(user_id) == movie_id:
        return game
    picks[user_id] = movie_id
    if len(picks) == len(game.players):
        return _resolve_winner(game, picks)
    return replace(game, picks=picks)


def finalize(game: Game) -> Game:
    if game.status != FINAL_ROUND:
        return game
    return _resolve_winner(game, dict(game.picks))


def end(game: Game) -> Game:
    if game.status == FINISHED:
        return game
    return replace(game, status=FINISHED, current=None, winner=None)


def reconcile(game: Game) -> Game:
    if game.status == FINISHED:
        return game
    players = game.players
    ready = frozenset(user for user in game.ready if user in players)
    votes: dict[int, dict[str, str]] = {}
    for movie_id, user_votes in game.votes.items():
        pruned = {user: choice for user, choice in user_votes.items() if user in players}
        if pruned:
            votes[movie_id] = pruned
    picks = {user: movie for user, movie in game.picks.items() if user in players and movie in game.candidates}
    cleaned = replace(game, ready=ready, votes=votes, picks=picks)

    if not players:
        return replace(cleaned, status=FINISHED, current=None, winner=None)
    if cleaned.status == READY:
        if cleaned.ready == players:
            return _start_playing(cleaned)
        return cleaned
    if cleaned.status == PLAYING:
        if cleaned.current is None or not 0 <= cleaned.pool_index < len(cleaned.pool):
            return _end_playing(replace(cleaned, current=None))
        if len(cleaned.votes.get(cleaned.current, {})) == len(players):
            return _decide_movie(cleaned, cleaned.current, cleaned.votes)
        return cleaned
    if cleaned.status == FINAL_ROUND:
        if not cleaned.candidates:
            return replace(cleaned, status=FINISHED, current=None, winner=None)
        if len(cleaned.picks) == len(players):
            return _resolve_winner(cleaned, cleaned.picks)
        return cleaned
    return cleaned


def _start_playing(game: Game) -> Game:
    if not game.pool:
        return replace(game, status=FINISHED, current=None, winner=None)
    return replace(game, status=PLAYING, pool_index=0, current=game.pool[0])


def _decide_movie(game: Game, movie_id: int, votes: dict[int, dict[str, str]]) -> Game:
    choices = [choice for user, choice in votes[movie_id].items() if user in game.players]
    advanced = len(choices) == len(game.players) and all(choice == INTERESTED for choice in choices)
    candidates = game.candidates
    if advanced and movie_id not in candidates and len(candidates) < FINALIST_COUNT:
        candidates = candidates + (movie_id,)
    if len(candidates) >= FINALIST_COUNT:
        return replace(game, status=FINAL_ROUND, votes=votes, candidates=candidates, current=None)
    return _next_movie(game, votes, candidates)


def _next_movie(game: Game, votes: dict[int, dict[str, str]], candidates: tuple[int, ...]) -> Game:
    next_index = game.pool_index + 1
    if next_index >= len(game.pool):
        return _end_playing(replace(game, votes=votes, candidates=candidates))
    return replace(
        game,
        votes=votes,
        candidates=candidates,
        pool_index=next_index,
        current=game.pool[next_index],
    )


def _end_playing(game: Game) -> Game:
    if game.candidates:
        return replace(game, status=FINAL_ROUND, current=None, winner=None)
    return replace(game, status=FINISHED, current=None, winner=None)


def _resolve_winner(game: Game, picks: dict[str, int]) -> Game:
    counts = {movie_id: 0 for movie_id in game.candidates}
    for user_id, movie_id in picks.items():
        if user_id in game.players and movie_id in counts:
            counts[movie_id] += 1
    winner = min(
        (movie_id for movie_id, count in counts.items() if count > 0),
        key=lambda movie_id: (-counts[movie_id], movie_id),
        default=None,
    )
    return replace(game, status=FINISHED, picks=picks, current=None, winner=winner)
