from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class LobbyChanged:
    lobby_id: UUID
    version: int
    reason: str


@dataclass(frozen=True)
class LobbyRestarted:
    lobby_id: UUID
    new_lobby_id: UUID


LobbyEvent = LobbyChanged | LobbyRestarted
LobbyCallback = Callable[[LobbyEvent], Awaitable[None]]
