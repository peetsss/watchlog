from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from starlette.responses import Response

from app.core.config import Settings
from app.core.sessions import (
    MemorySessionStore,
    SessionData,
    hash_session_id,
    new_session,
    set_auth_cookies,
    ttl_for,
)


def test_session_data_requires_matching_identity() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        SessionData(kind="member", csrf="token", created_at=now, last_seen=now)

    with pytest.raises(ValidationError):
        SessionData(kind="guest", csrf="token", created_at=now, last_seen=now)

    with pytest.raises(ValidationError):
        SessionData(kind="anonymous", user_id=1, csrf="token", created_at=now, last_seen=now)


async def test_memory_store_round_trip_and_rotation() -> None:
    store = MemorySessionStore()
    data = new_session("member", user_id=42)

    session_id = await store.create(data, 60)
    assert await store.get(session_id) == data

    rotated_id = await store.rotate(session_id, data.model_copy(update={"csrf": "new"}), 60)

    assert rotated_id != session_id
    assert await store.get(session_id) is None
    rotated = await store.get(rotated_id)
    assert rotated is not None
    assert rotated.csrf == "new"

    await store.delete(rotated_id)
    assert await store.get(rotated_id) is None


async def test_memory_store_expires_sessions() -> None:
    now = [1000.0]
    store = MemorySessionStore(clock=lambda: now[0])
    session_id = await store.create(new_session("anonymous"), ttl=10)

    now[0] += 9
    assert await store.get(session_id) is not None

    now[0] += 2
    assert await store.get(session_id) is None


async def test_touch_extends_the_session() -> None:
    now = [1000.0]
    store = MemorySessionStore(clock=lambda: now[0])
    session_id = await store.create(new_session("anonymous"), ttl=10)

    now[0] += 9
    await store.touch(session_id, ttl=10)
    now[0] += 9

    assert await store.get(session_id) is not None


async def test_revoke_user_sessions_keeps_anonymous_sessions() -> None:
    store = MemorySessionStore()
    first = await store.create(new_session("member", user_id=42), ttl=60)
    second = await store.create(new_session("member", user_id=42), ttl=60)
    anonymous = await store.create(new_session("anonymous"), ttl=60)

    await store.revoke_user_sessions(42)

    assert await store.get(first) is None
    assert await store.get(second) is None
    assert await store.get(anonymous) is not None


async def test_rotated_session_stays_in_the_user_index() -> None:
    store = MemorySessionStore()
    original = await store.create(new_session("member", user_id=42), ttl=60)
    rotated = await store.rotate(original, new_session("member", user_id=42), ttl=60)

    await store.revoke_user_sessions(42)

    assert await store.get(rotated) is None


def test_session_id_hash_is_stable_and_one_way() -> None:
    session_id = "a-secret-session-id"

    digest = hash_session_id(session_id)

    assert digest == hash_session_id(session_id)
    assert len(digest) == 64
    assert session_id not in digest


def test_auth_cookies_use_security_flags() -> None:
    settings = Settings(
        _env_file=None,
        env="prod",
        secret_key="a" * 32,
        public_url="https://watchlog.example",
        database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
        allowed_hosts="watchlog.example",
        trusted_origins="https://watchlog.example",
        trusted_proxy_ips="172.18.0.0/16",
        docs_enabled=False,
        mail_backend="resend",
        mail_from="watchlog <hello@watchlog.example>",
        resend_api_key="re_test",
    )
    response = Response()
    data = new_session("member", user_id=1)

    set_auth_cookies(response, "session-id", data, settings)

    cookies = response.headers.getlist("set-cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith("__Host-wl_session="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("wl_csrf="))

    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Path=/" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie


def test_ttl_for_uses_the_session_kind() -> None:
    settings = Settings(
        _env_file=None,
        session_ttl_seconds=100,
        guest_session_ttl_seconds=50,
        anonymous_session_ttl_seconds=10,
    )

    assert ttl_for("member", settings) == 100
    assert ttl_for("guest", settings) == 50
    assert ttl_for("anonymous", settings) == 10
