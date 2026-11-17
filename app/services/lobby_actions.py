from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.lobby.exceptions import InvalidActionError, InvalidChoiceError
from app.models.lobby import Lobby
from app.services import lobby as lobby_service
from app.services.identity import Viewer


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


async def perform_action(
    db: AsyncSession,
    lobby_id: UUID,
    viewer: Viewer,
    action: str,
    payload: Mapping[str, object],
) -> Lobby:
    if action == "ready":
        return await lobby_service.mark_ready(db, lobby_id, viewer)
    if action == "unready":
        return await lobby_service.unready(db, lobby_id, viewer)
    if action == "start":
        return await lobby_service.start_lobby(db, lobby_id, viewer)
    if action == "vote":
        return await lobby_service.vote(db, lobby_id, viewer, _movie_id(payload), _choice(payload))
    if action == "pick":
        return await lobby_service.pick(db, lobby_id, viewer, _movie_id(payload))
    if action == "advance":
        return await lobby_service.advance(db, lobby_id, viewer)
    if action == "next_round":
        return await lobby_service.next_round(db, lobby_id, viewer)
    if action == "finalize":
        return await lobby_service.finalize_lobby(db, lobby_id, viewer)
    if action == "leave":
        return await lobby_service.leave_lobby(db, lobby_id, viewer)
    if action == "end":
        return await lobby_service.end_lobby(db, lobby_id, viewer)
    if action == "restart":
        return await lobby_service.restart_lobby(db, lobby_id, viewer)
    raise InvalidActionError(f"Unknown lobby action: {action!r}")
