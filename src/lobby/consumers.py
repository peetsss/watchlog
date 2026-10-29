import logging
from collections.abc import Mapping
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from lobby import actions, selectors
from lobby.dto import LobbyState
from lobby.errors import error_details
from lobby.exceptions import LobbyError, LobbyNotFoundError, NotAMemberError
from lobby.models import Lobby
from lobby.realtime import lobby_group_name
from lobby.serializers import state_to_dict
from user.models import User

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404


@database_sync_to_async
def _load_state(lobby_uuid: str, user: User) -> tuple[LobbyState | None, str | None]:
    if not user.is_authenticated:
        return None, "unauthorized"
    try:
        return selectors.get_state(lobby_uuid, user), None
    except LobbyNotFoundError:
        return None, "not_found"
    except NotAMemberError:
        return None, "not_member"


@database_sync_to_async
def _perform_action(lobby_uuid: str, user: User, action: str, payload: Mapping[str, object]) -> Lobby:
    return actions.perform_action(lobby_uuid, user, action, payload)


class LobbyConsumer(AsyncJsonWebsocketConsumer):
    lobby_uuid: str
    group_name: str

    async def connect(self) -> None:
        self.lobby_uuid = str(self.scope["url_route"]["kwargs"]["lobby_uuid"])
        self.group_name = lobby_group_name(self.lobby_uuid)
        state, error = await _load_state(self.lobby_uuid, self.scope["user"])
        if error == "unauthorized":
            await self.close(code=CLOSE_UNAUTHORIZED)
            return
        if error == "not_found":
            await self.close(code=CLOSE_NOT_FOUND)
            return
        if error is not None or state is None:
            await self.close(code=CLOSE_FORBIDDEN)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "lobby.state", "lobby": state_to_dict(state)})

    async def disconnect(self, code: int) -> None:
        group_name = getattr(self, "group_name", None)
        if group_name is not None:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, content: dict[str, object], **kwargs: object) -> None:
        if not isinstance(content, dict):
            await self._send_error("invalid_action", "Message must be a JSON object")
            return
        action = content.get("action")
        if not isinstance(action, str):
            await self._send_error("invalid_action", "action must be a string")
            return
        if action == "state.get":
            await self._send_current_state()
            return
        try:
            lobby = await _perform_action(self.lobby_uuid, self.scope["user"], action, content)
        except LobbyError as exc:
            _, code = error_details(exc)
            await self._send_error(code, str(exc))
            return
        except Exception:
            logger.exception("Unexpected lobby websocket action failure")
            await self._send_error("server_error", "The action could not be completed.")
            return

        if action == "leave":
            await self.send_json({"type": "lobby.left"})
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.close(code=4000)
            return
        if action == "restart":
            state, error = await _load_state(str(lobby.uuid), self.scope["user"])
            if state is None:
                await self._send_error(error or "not_found", "The new room could not be loaded.")
                return
            await self.send_json(
                {
                    "type": "lobby.restarted",
                    "previous_uuid": self.lobby_uuid,
                    "new_lobby_uuid": str(lobby.uuid),
                    "lobby": state_to_dict(state),
                }
            )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.close(code=4001)
            return

        await self._send_state(lobby.uuid)

    async def _send_current_state(self) -> None:
        state, error = await _load_state(self.lobby_uuid, self.scope["user"])
        if state is None:
            await self._send_error(error or "not_found", "The room is no longer available.")
            return
        await self.send_json({"type": "lobby.state", "lobby": state_to_dict(state)})

    async def _send_state(self, lobby_uuid: str | UUID) -> None:
        state, error = await _load_state(str(lobby_uuid), self.scope["user"])
        if state is None:
            await self._send_error(error or "not_found", "The room is no longer available.")
            return
        await self.send_json({"type": "lobby.state", "lobby": state_to_dict(state)})

    async def _send_error(self, code: str, message: str) -> None:
        await self.send_json({"type": "lobby.error", "code": code, "message": message})

    async def lobby_changed(self, event: dict[str, object]) -> None:
        state, error = await _load_state(self.lobby_uuid, self.scope["user"])
        if state is None:
            await self.send_json({"type": "lobby.removed", "reason": error or "not_member"})
            await self.close(code=CLOSE_FORBIDDEN)
            return
        await self.send_json(
            {
                "type": "lobby.state",
                "lobby": state_to_dict(state),
                "reason": event.get("reason"),
            }
        )

    async def lobby_restarted(self, event: dict[str, object]) -> None:
        await self.send_json(
            {
                "type": "lobby.restarted",
                "previous_uuid": event.get("lobby_uuid"),
                "new_lobby_uuid": event.get("new_lobby_uuid"),
            }
        )
        await self.close(code=4001)
