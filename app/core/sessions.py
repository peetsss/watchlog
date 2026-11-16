import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from redis.asyncio import Redis
from starlette.responses import Response

from app.core.config import Settings

logger = logging.getLogger(__name__)

SessionKind = Literal["member", "guest", "anonymous"]

SESSION_PREFIX = "watchlog:sess:"
SESSION_ID_BYTES = 32
CSRF_TOKEN_BYTES = 32


class SessionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SessionKind
    user_id: int | None = None
    guest_id: UUID | None = None
    csrf: str
    created_at: datetime
    last_seen: datetime

    @model_validator(mode="after")
    def validate_identity(self) -> SessionData:
        if self.kind == "member" and (self.user_id is None or self.guest_id is not None):
            raise ValueError("A member session requires user_id and no guest_id")
        if self.kind == "guest" and (self.guest_id is None or self.user_id is not None):
            raise ValueError("A guest session requires guest_id and no user_id")
        if self.kind == "anonymous" and (self.user_id is not None or self.guest_id is not None):
            raise ValueError("An anonymous session cannot have an identity")
        return self


def new_session_id() -> str:
    return secrets.token_urlsafe(SESSION_ID_BYTES)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def hash_session_id(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def new_session(kind: SessionKind, *, user_id: int | None = None, guest_id: UUID | None = None) -> SessionData:
    now = datetime.now(UTC)
    return SessionData(
        kind=kind,
        user_id=user_id,
        guest_id=guest_id,
        csrf=new_csrf_token(),
        created_at=now,
        last_seen=now,
    )


def ttl_for(kind: SessionKind, settings: Settings) -> int:
    if kind == "member":
        return settings.session_ttl_seconds
    if kind == "guest":
        return settings.guest_session_ttl_seconds
    return settings.anonymous_session_ttl_seconds


class SessionStore(Protocol):
    async def create(self, data: SessionData, ttl: int) -> str: ...

    async def get(self, session_id: str) -> SessionData | None: ...

    async def save(self, session_id: str, data: SessionData, ttl: int) -> None: ...

    async def touch(self, session_id: str, ttl: int) -> None: ...

    async def delete(self, session_id: str) -> None: ...

    async def rotate(self, session_id: str, data: SessionData, ttl: int) -> str: ...


class RedisSessionStore:
    def __init__(self, redis: Redis, prefix: str = SESSION_PREFIX) -> None:
        self._redis = redis
        self._prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{hash_session_id(session_id)}"

    async def create(self, data: SessionData, ttl: int) -> str:
        session_id = new_session_id()
        await self._redis.set(self._key(session_id), data.model_dump_json(), ex=ttl)
        return session_id

    async def get(self, session_id: str) -> SessionData | None:
        key = self._key(session_id)
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            return SessionData.model_validate_json(raw)
        except ValueError:
            logger.warning("Discarding a malformed session record")
            await self._redis.delete(key)
            return None

    async def save(self, session_id: str, data: SessionData, ttl: int) -> None:
        await self._redis.set(self._key(session_id), data.model_dump_json(), ex=ttl)

    async def touch(self, session_id: str, ttl: int) -> None:
        await self._redis.expire(self._key(session_id), ttl)

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))

    async def rotate(self, session_id: str, data: SessionData, ttl: int) -> str:
        new_id = await self.create(data, ttl)
        await self.delete(session_id)
        return new_id


@dataclass
class _MemoryEntry:
    data: SessionData
    expires_at: float


class MemorySessionStore:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._entries: dict[str, _MemoryEntry] = {}

    async def create(self, data: SessionData, ttl: int) -> str:
        session_id = new_session_id()
        self._entries[session_id] = _MemoryEntry(data=data, expires_at=self._clock() + ttl)
        return session_id

    async def get(self, session_id: str) -> SessionData | None:
        entry = self._entries.get(session_id)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._entries.pop(session_id, None)
            return None
        return entry.data

    async def save(self, session_id: str, data: SessionData, ttl: int) -> None:
        self._entries[session_id] = _MemoryEntry(data=data, expires_at=self._clock() + ttl)

    async def touch(self, session_id: str, ttl: int) -> None:
        entry = self._entries.get(session_id)
        if entry is not None:
            entry.expires_at = self._clock() + ttl

    async def delete(self, session_id: str) -> None:
        self._entries.pop(session_id, None)

    async def rotate(self, session_id: str, data: SessionData, ttl: int) -> str:
        new_id = await self.create(data, ttl)
        await self.delete(session_id)
        return new_id


def set_session_cookie(response: Response, session_id: str, data: SessionData, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=ttl_for(data.kind, settings),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def set_csrf_cookie(response: Response, data: SessionData, settings: Settings) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=data.csrf,
        max_age=ttl_for(data.kind, settings),
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def set_auth_cookies(response: Response, session_id: str, data: SessionData, settings: Settings) -> None:
    set_session_cookie(response, session_id, data, settings)
    set_csrf_cookie(response, data, settings)


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )
