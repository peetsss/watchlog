from collections.abc import Mapping
from uuid import UUID

from lobby import services
from lobby.exceptions import InvalidActionError, InvalidChoiceError
from lobby.models import Lobby
from user.models import User

__all__ = ["perform_action"]


def _movie_id(payload: Mapping[str, object]) -> int:
    raw = payload.get("movie_id")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise InvalidChoiceError("movie_id must be a positive integer")
    return raw


def _choice(payload: Mapping[str, object]) -> str:
    raw = payload.get("choice")
    if not isinstance(raw, str):
        raise InvalidChoiceError("choice must be a string")
    return raw


def perform_action(lobby_uuid: str | UUID, user: User, action: str, payload: Mapping[str, object]) -> Lobby:
    if action == "ready":
        return services.mark_ready(lobby_uuid, user)
    if action == "unready":
        return services.unready(lobby_uuid, user)
    if action == "start":
        return services.start_lobby(lobby_uuid, user)
    if action == "vote":
        return services.vote(lobby_uuid, user, _movie_id(payload), _choice(payload))
    if action == "pick":
        return services.pick(lobby_uuid, user, _movie_id(payload))
    if action == "advance":
        return services.advance(lobby_uuid, user)
    if action == "next_round":
        return services.next_round(lobby_uuid, user)
    if action == "finalize":
        return services.finalize_lobby(lobby_uuid, user)
    if action == "leave":
        return services.leave_lobby(lobby_uuid, user)
    if action == "end":
        return services.end_lobby(lobby_uuid, user)
    if action == "restart":
        return services.restart_lobby(lobby_uuid, user)
    raise InvalidActionError(f"Unknown lobby action: {action!r}")
