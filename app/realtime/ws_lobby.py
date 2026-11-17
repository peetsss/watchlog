import logging
from http.cookies import CookieError, SimpleCookie
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import _resolve_lobby_viewer
from app.core.config import Settings
from app.domain.lobby.errors import error_details
from app.domain.lobby.exceptions import LobbyError, LobbyNotFoundError, NotAMemberError
from app.realtime.events import LobbyEvent, LobbyRestarted
from app.schemas.lobby import LobbyState
from app.services import lobby as lobby_service
from app.services import lobby_actions
from app.services.identity import Viewer

logger = logging.getLogger(__name__)

router = APIRouter()

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
CLOSE_LEFT = 4000
CLOSE_RESTARTED = 4001

_ACTION_ALIASES = {
    "ready": "ready",
    "unready": "unready",
    "start": "start",
    "vote": "vote",
    "pick": "pick",
    "advance": "advance",
    "next-round": "next_round",
    "next_round": "next_round",
    "finalize": "finalize",
    "leave": "leave",
    "end": "end",
    "restart": "restart",
}


def _cookie_value(websocket: WebSocket, name: str) -> str | None:
    header = websocket.headers.get("cookie")
    if not header:
        return None
    cookies = SimpleCookie()
    try:
        cookies.load(header)
    except CookieError:
        return None
    morsel = cookies.get(name)
    return morsel.value if morsel is not None else None


async def _authenticate(websocket: WebSocket) -> Viewer | None:
    settings: Settings = websocket.app.state.settings
    session_id = _cookie_value(websocket, settings.session_cookie_name)
    if session_id is None:
        return None
    try:
        data = await websocket.app.state.session_store.get(session_id)
    except Exception:
        logger.exception("Failed to load the websocket session")
        return None
    if data is None:
        return None
    async with websocket.app.state.sessionmaker() as session:
        return await _resolve_lobby_viewer(data, session, settings)


async def _load_state(
    websocket: WebSocket,
    lobby_id: UUID,
    viewer: Viewer,
) -> tuple[LobbyState | None, str | None]:
    async with websocket.app.state.sessionmaker() as session:
        try:
            return await lobby_service.get_state(session, lobby_id, viewer), None
        except LobbyNotFoundError:
            return None, "not_found"
        except NotAMemberError:
            return None, "not_member"
        except LobbyError:
            logger.exception("Failed to load the websocket lobby state")
            return None, "error"


async def _safe_send(websocket: WebSocket, payload: dict[str, object]) -> None:
    try:
        await websocket.send_json(payload)
    except RuntimeError, WebSocketDisconnect:
        logger.debug("Websocket closed before a message could be sent")


async def _safe_close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        logger.debug("Websocket was already closed")


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    await _safe_send(websocket, {"type": "lobby.error", "code": code, "message": message})


def _state_payload(state: LobbyState, reason: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"type": "lobby.state", "lobby": state.model_dump(mode="json")}
    if reason is not None:
        payload["reason"] = reason
    return payload


@router.websocket("/ws/lobby/{lobby_uuid}/")
async def lobby_socket(websocket: WebSocket, lobby_uuid: UUID) -> None:
    settings: Settings = websocket.app.state.settings
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in settings.trusted_origins:
        await _safe_close(websocket, CLOSE_FORBIDDEN)
        return

    viewer = await _authenticate(websocket)
    if viewer is None:
        await _safe_close(websocket, CLOSE_UNAUTHORIZED)
        return

    state, error = await _load_state(websocket, lobby_uuid, viewer)
    if state is None:
        await _safe_close(websocket, CLOSE_NOT_FOUND if error == "not_found" else CLOSE_FORBIDDEN)
        return

    await websocket.accept()
    await _safe_send(websocket, _state_payload(state))
    holder: dict[str, object] = {"last_version": state.version, "closing": False, "restarted": False}
    hub = websocket.app.state.hub

    async def on_event(event: LobbyEvent) -> None:
        if holder["closing"]:
            return
        if isinstance(event, LobbyRestarted):
            if event.lobby_id != lobby_uuid:
                return
            holder["closing"] = True
            holder["restarted"] = True
            await _safe_send(
                websocket,
                {
                    "type": "lobby.restarted",
                    "previous_uuid": str(event.lobby_id),
                    "new_lobby_uuid": str(event.new_lobby_id),
                },
            )
            await _safe_close(websocket, CLOSE_RESTARTED)
            return
        last_version = int(holder["last_version"])
        if event.version <= last_version:
            return
        current, reason = await _load_state(websocket, lobby_uuid, viewer)
        if current is None:
            holder["closing"] = True
            await _safe_send(websocket, {"type": "lobby.removed", "reason": reason or "not_member"})
            await _safe_close(websocket, CLOSE_FORBIDDEN)
            return
        holder["last_version"] = current.version
        await _safe_send(websocket, _state_payload(current, event.reason))

    await hub.register(lobby_uuid, on_event)
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            if not isinstance(message, dict):
                await _send_error(websocket, "invalid_action", "Message must be a JSON object")
                continue
            action = message.get("action")
            if not isinstance(action, str):
                await _send_error(websocket, "invalid_action", "action must be a string")
                continue

            if action == "state.get":
                current, reason = await _load_state(websocket, lobby_uuid, viewer)
                if current is None:
                    await _send_error(websocket, reason or "not_found", "The room is no longer available.")
                    continue
                holder["last_version"] = current.version
                await _safe_send(websocket, _state_payload(current))
                continue

            action_name = _ACTION_ALIASES.get(action)
            if action_name is None:
                await _send_error(websocket, "invalid_action", f"Unknown lobby action: {action!r}")
                continue

            if action_name == "leave":
                holder["closing"] = True
                try:
                    async with websocket.app.state.sessionmaker() as session:
                        session.info["lobby_publisher"] = hub.publish
                        await lobby_actions.perform_action(session, lobby_uuid, viewer, "leave", message)
                except LobbyError as exc:
                    holder["closing"] = False
                    _, code = error_details(exc)
                    await _send_error(websocket, code, str(exc))
                    continue
                except Exception:
                    holder["closing"] = False
                    logger.exception("Unexpected lobby websocket leave failure")
                    await _send_error(websocket, "server_error", "The action could not be completed.")
                    continue
                await _safe_send(websocket, {"type": "lobby.left"})
                await _safe_close(websocket, CLOSE_LEFT)
                break

            try:
                async with websocket.app.state.sessionmaker() as session:
                    session.info["lobby_publisher"] = hub.publish
                    lobby = await lobby_actions.perform_action(session, lobby_uuid, viewer, action_name, message)
            except LobbyError as exc:
                _, code = error_details(exc)
                await _send_error(websocket, code, str(exc))
                continue
            except Exception:
                logger.exception("Unexpected lobby websocket action failure")
                await _send_error(websocket, "server_error", "The action could not be completed.")
                continue

            if action_name == "restart":
                if not holder["restarted"]:
                    holder["closing"] = True
                    holder["restarted"] = True
                    await _safe_send(
                        websocket,
                        {
                            "type": "lobby.restarted",
                            "previous_uuid": str(lobby_uuid),
                            "new_lobby_uuid": str(lobby.id),
                        },
                    )
                    await _safe_close(websocket, CLOSE_RESTARTED)
                break

            current, reason = await _load_state(websocket, lobby_uuid, viewer)
            if current is None:
                holder["closing"] = True
                await _safe_send(websocket, {"type": "lobby.removed", "reason": reason or "not_member"})
                await _safe_close(websocket, CLOSE_FORBIDDEN)
                break
            if current.version > int(holder["last_version"]):
                holder["last_version"] = current.version
                await _safe_send(websocket, _state_payload(current))
    finally:
        await hub.unregister(lobby_uuid, on_event)
