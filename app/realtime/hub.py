import asyncio
import json
import logging
from contextlib import suppress
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.realtime.events import LobbyCallback, LobbyChanged, LobbyEvent, LobbyRestarted

logger = logging.getLogger(__name__)

LOBBY_CHANNEL_PREFIX = "watchlog:lobby:"
SUBSCRIPTION_TIMEOUT_SECONDS = 5.0


class LobbyHub(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def register(self, lobby_id: UUID, callback: LobbyCallback) -> None: ...

    async def unregister(self, lobby_id: UUID, callback: LobbyCallback) -> None: ...

    async def publish(self, event: LobbyEvent) -> None: ...


class MemoryLobbyHub:
    def __init__(self) -> None:
        self._callbacks: dict[UUID, set[LobbyCallback]] = {}

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._callbacks.clear()

    async def register(self, lobby_id: UUID, callback: LobbyCallback) -> None:
        self._callbacks.setdefault(lobby_id, set()).add(callback)

    async def unregister(self, lobby_id: UUID, callback: LobbyCallback) -> None:
        callbacks = self._callbacks.get(lobby_id)
        if callbacks is None:
            return
        callbacks.discard(callback)
        if not callbacks:
            self._callbacks.pop(lobby_id, None)

    async def publish(self, event: LobbyEvent) -> None:
        for callback in list(self._callbacks.get(event.lobby_id, ())):
            try:
                await callback(event)
            except Exception:
                logger.exception("Memory lobby callback failed")


def serialize_event(event: LobbyEvent) -> str:
    if isinstance(event, LobbyChanged):
        payload = {
            "type": "lobby.changed",
            "lobby_id": str(event.lobby_id),
            "version": event.version,
            "reason": event.reason,
        }
    else:
        payload = {
            "type": "lobby.restarted",
            "lobby_id": str(event.lobby_id),
            "new_lobby_id": str(event.new_lobby_id),
        }
    return json.dumps(payload)


def deserialize_event(raw: str) -> LobbyEvent | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Discarding malformed lobby event")
        return None
    if not isinstance(payload, dict):
        return None
    try:
        if payload.get("type") == "lobby.changed":
            return LobbyChanged(
                lobby_id=UUID(str(payload["lobby_id"])),
                version=int(payload["version"]),
                reason=str(payload.get("reason", "change")),
            )
        if payload.get("type") == "lobby.restarted":
            return LobbyRestarted(
                lobby_id=UUID(str(payload["lobby_id"])),
                new_lobby_id=UUID(str(payload["new_lobby_id"])),
            )
    except KeyError, TypeError, ValueError:
        logger.warning("Discarding malformed lobby event")
        return None
    return None


class RedisLobbyHub:
    def __init__(self, redis: Redis, prefix: str = LOBBY_CHANNEL_PREFIX) -> None:
        self._redis = redis
        self._prefix = prefix
        self._callbacks: dict[UUID, set[LobbyCallback]] = {}
        self._pubsub = None
        self._task: asyncio.Task[None] | None = None
        self._closed = False
        self._ready = asyncio.Event()

    def _channel(self, lobby_id: UUID) -> str:
        return f"{self._prefix}{lobby_id}"

    async def start(self) -> None:
        self._closed = False
        self._ready.clear()
        self._task = asyncio.create_task(self._listen())
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=SUBSCRIPTION_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("Redis lobby subscription was not ready at startup")

    async def stop(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        self._callbacks.clear()

    async def _listen(self) -> None:
        while not self._closed:
            try:
                self._pubsub = self._redis.pubsub()
                await self._pubsub.psubscribe(f"{self._prefix}*")
                self._ready.set()
                async for message in self._pubsub.listen():
                    if message.get("type") != "pmessage":
                        continue
                    event = deserialize_event(message.get("data", ""))
                    if event is not None:
                        await self._dispatch(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis lobby subscription failed")
                if self._pubsub is not None:
                    with suppress(Exception):
                        await self._pubsub.aclose()
                    self._pubsub = None
                await asyncio.sleep(1)

    async def _dispatch(self, event: LobbyEvent) -> None:
        for callback in list(self._callbacks.get(event.lobby_id, ())):
            try:
                await callback(event)
            except Exception:
                logger.exception("Redis lobby callback failed")

    async def register(self, lobby_id: UUID, callback: LobbyCallback) -> None:
        self._callbacks.setdefault(lobby_id, set()).add(callback)

    async def unregister(self, lobby_id: UUID, callback: LobbyCallback) -> None:
        callbacks = self._callbacks.get(lobby_id)
        if callbacks is None:
            return
        callbacks.discard(callback)
        if not callbacks:
            self._callbacks.pop(lobby_id, None)

    async def publish(self, event: LobbyEvent) -> None:
        try:
            await self._redis.publish(self._channel(event.lobby_id), serialize_event(event))
        except Exception:
            logger.exception("Failed to publish a lobby event")
