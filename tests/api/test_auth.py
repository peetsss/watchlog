from datetime import UTC, datetime, timedelta

import psycopg
import pytest
import time_machine
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from tests.conftest import _database_url

REGISTER = {"username": "alice", "email": "alice@example.com", "password": "correct horse"}
LOGIN = {"identifier": "alice", "password": "correct horse"}


async def csrf_token(client: AsyncClient) -> str:
    response = await client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def csrf_headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token}


def current_csrf(client: AsyncClient) -> str:
    token = client.cookies.get("wl_csrf")
    assert token
    return token


def latest_outbox(settings: Settings, template: str) -> dict:
    with psycopg.connect(_database_url(settings)) as connection:
        row = connection.execute(
            "SELECT payload FROM email_outbox WHERE template = %s ORDER BY id DESC LIMIT 1",
            (template,),
        ).fetchone()
    assert row is not None
    return row[0]


async def register(client: AsyncClient, token: str) -> dict:
    response = await client.post("/api/auth/register", json=REGISTER, headers=csrf_headers(token))
    assert response.status_code == 201
    return response.json()["viewer"]


async def test_csrf_bootstraps_an_anonymous_session(client: AsyncClient) -> None:
    response = await client.get("/api/auth/csrf")

    assert response.status_code == 200
    assert response.json()["csrfToken"]
    assert client.cookies.get("wl_session")
    assert client.cookies.get("wl_csrf")


async def test_private_api_responses_are_not_cached(client: AsyncClient) -> None:
    csrf_response = await client.get("/api/auth/csrf")
    assert csrf_response.headers["cache-control"] == "no-store"

    await register(client, current_csrf(client))

    me = await client.get("/api/me")
    assert me.headers["cache-control"] == "no-store"
    session = await client.get("/api/auth/session")
    assert session.headers["cache-control"] == "no-store"


async def test_register_me_logout_and_login(client: AsyncClient) -> None:
    token = await csrf_token(client)
    viewer = await register(client, token)

    assert viewer["mode"] == "member"
    assert viewer["username"] == "alice"
    assert viewer["initials"] == "AL"
    assert viewer["color"].startswith("#")
    assert viewer["email_verified"] is False

    member_session = client.cookies.get("wl_session")
    member_token = client.cookies.get("wl_csrf")
    assert member_session
    assert member_token
    assert member_token != token

    me = await client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["viewer"] == viewer
    assert me.json()["stats"] == {"titles_watched": 0, "average_score": None}
    assert me.json()["email"] == "alice@example.com"

    logout = await client.post("/api/auth/logout", headers=csrf_headers(member_token))
    assert logout.status_code == 204
    assert client.cookies.get("wl_session") is None
    assert (await client.get("/api/me")).status_code == 401

    token = await csrf_token(client)
    login = await client.post("/api/auth/login", json=LOGIN, headers=csrf_headers(token))

    assert login.status_code == 200
    assert login.json()["viewer"]["username"] == "alice"
    assert client.cookies.get("wl_session") != member_session


async def test_register_without_csrf_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json=REGISTER)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


async def test_register_with_wrong_csrf_is_rejected(client: AsyncClient) -> None:
    await csrf_token(client)

    response = await client.post("/api/auth/register", json=REGISTER, headers=csrf_headers("wrong"))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


async def test_register_rejects_a_disallowed_origin(client: AsyncClient) -> None:
    token = await csrf_token(client)

    response = await client.post(
        "/api/auth/register",
        json=REGISTER,
        headers={**csrf_headers(token), "Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


async def test_register_accepts_a_trusted_origin(client: AsyncClient) -> None:
    token = await csrf_token(client)

    response = await client.post(
        "/api/auth/register",
        json=REGISTER,
        headers={**csrf_headers(token), "Origin": "http://localhost:5173"},
    )

    assert response.status_code == 201


async def test_session_id_rotates_on_register(client: AsyncClient) -> None:
    token = await csrf_token(client)
    anonymous_session = client.cookies.get("wl_session")

    await register(client, token)

    assert client.cookies.get("wl_session") != anonymous_session


async def test_duplicate_username_is_rejected(client: AsyncClient) -> None:
    token = await csrf_token(client)
    await register(client, token)
    member_token = client.cookies.get("wl_csrf")
    await client.post("/api/auth/logout", headers=csrf_headers(member_token))

    token = await csrf_token(client)
    response = await client.post("/api/auth/register", json=REGISTER, headers=csrf_headers(token))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_taken"


async def test_csrf_bootstrap_is_rate_limited(client: AsyncClient) -> None:
    for _ in range(60):
        response = await client.get("/api/auth/csrf")
        assert response.status_code == 200

    blocked = await client.get("/api/auth/csrf")

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.headers["Retry-After"]


async def test_registration_is_rate_limited(client: AsyncClient) -> None:
    await csrf_token(client)
    for index in range(5):
        response = await client.post(
            "/api/auth/register",
            json={
                "username": f"rate_user_{index}",
                "email": f"rate_user_{index}@example.com",
                "password": "correct horse",
            },
            headers=csrf_headers(current_csrf(client)),
        )
        assert response.status_code == 201

    blocked = await client.post(
        "/api/auth/register",
        json={
            "username": "rate_user_blocked",
            "email": "rate_user_blocked@example.com",
            "password": "correct horse",
        },
        headers=csrf_headers(current_csrf(client)),
    )

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.headers["Retry-After"]


async def test_duplicate_email_is_rejected(client: AsyncClient) -> None:
    token = await csrf_token(client)
    await register(client, token)
    member_token = client.cookies.get("wl_csrf")
    await client.post("/api/auth/logout", headers=csrf_headers(member_token))

    token = await csrf_token(client)
    response = await client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "alice@example.com", "password": "correct horse"},
        headers=csrf_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_invalid_credentials_are_rejected(client: AsyncClient) -> None:
    token = await csrf_token(client)
    response = await client.post(
        "/api/auth/login",
        json={"identifier": "nobody", "password": "wrong password"},
        headers=csrf_headers(token),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "email": "alice@example.com", "password": "long enough"},
        {"username": "bad name", "email": "alice@example.com", "password": "long enough"},
        {"username": "alice", "password": "long enough"},
        {"username": "alice", "email": "not-an-email", "password": "long enough"},
        {"username": "alice", "email": "alice@example.com", "password": "short"},
        {"username": "alice", "email": "alice@example.com", "password": "12345678"},
        {"username": "alice", "email": "alice@example.com", "password": "alice"},
    ],
)
async def test_invalid_registration_payloads(client: AsyncClient, payload: dict[str, str]) -> None:
    token = await csrf_token(client)

    response = await client.post("/api/auth/register", json=payload, headers=csrf_headers(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_logout_revokes_the_server_side_session(client: AsyncClient) -> None:
    token = await csrf_token(client)
    await register(client, token)
    member_session = client.cookies.get("wl_session")
    member_token = client.cookies.get("wl_csrf")

    await client.post("/api/auth/logout", headers=csrf_headers(member_token))

    response = await client.get("/api/me", headers={"Cookie": f"wl_session={member_session}"})
    assert response.status_code == 401


async def test_expired_session_is_rejected(client: AsyncClient) -> None:
    token = await csrf_token(client)
    await register(client, token)

    with time_machine.travel(datetime.now(UTC) + timedelta(days=15), tick=False):
        response = await client.get("/api/me")

    assert response.status_code == 401


async def test_email_verification_marks_the_account_verified(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    token = await csrf_token(client)
    await register(client, token)
    assert (await client.get("/api/me")).json()["viewer"]["email_verified"] is False
    verification = latest_outbox(test_settings, "verify_email")

    response = await client.post(
        "/api/auth/verify-email",
        json={"token": verification["token"]},
        headers=csrf_headers(current_csrf(client)),
    )

    assert response.status_code == 204
    me = await client.get("/api/me")
    assert me.json()["viewer"]["email_verified"] is True
    assert me.json()["email"] == "alice@example.com"


async def test_resend_invalidates_the_previous_verification_token(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    token = await csrf_token(client)
    await register(client, token)
    initial = latest_outbox(test_settings, "verify_email")["token"]

    response = await client.post(
        "/api/auth/resend-verification",
        json={"email": "alice@example.com"},
        headers=csrf_headers(current_csrf(client)),
    )

    assert response.status_code == 202
    replacement = latest_outbox(test_settings, "verify_email")["token"]
    assert (
        await client.post(
            "/api/auth/verify-email",
            json={"token": initial},
            headers=csrf_headers(current_csrf(client)),
        )
    ).status_code == 400
    assert (
        await client.post(
            "/api/auth/verify-email",
            json={"token": replacement},
            headers=csrf_headers(current_csrf(client)),
        )
    ).status_code == 204


async def test_password_reset_changes_the_password_and_revokes_sessions(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    token = await csrf_token(client)
    await register(client, token)
    verification = latest_outbox(test_settings, "verify_email")
    await client.post(
        "/api/auth/verify-email",
        json={"token": verification["token"]},
        headers=csrf_headers(current_csrf(client)),
    )
    member_token = current_csrf(client)

    response = await client.post(
        "/api/auth/forgot-password",
        json={"email": "alice@example.com"},
        headers=csrf_headers(member_token),
    )
    assert response.status_code == 202
    reset = latest_outbox(test_settings, "reset_password")

    reset_response = await client.post(
        "/api/auth/reset-password",
        json={"token": reset["token"], "new_password": "new correct horse"},
        headers=csrf_headers(member_token),
    )
    assert reset_response.status_code == 204
    assert (await client.get("/api/me")).status_code == 401

    token = await csrf_token(client)
    login = await client.post(
        "/api/auth/login",
        json={"identifier": "alice@example.com", "password": "new correct horse"},
        headers=csrf_headers(token),
    )
    assert login.status_code == 200


async def test_change_email_requires_confirmation_at_the_new_address(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    token = await csrf_token(client)
    await register(client, token)
    verification = latest_outbox(test_settings, "verify_email")
    await client.post(
        "/api/auth/verify-email",
        json={"token": verification["token"]},
        headers=csrf_headers(current_csrf(client)),
    )

    response = await client.post(
        "/api/auth/change-email",
        json={"new_email": "new@example.com", "password": "correct horse"},
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 202
    confirmation = latest_outbox(test_settings, "verify_email")
    assert confirmation["token"]

    await client.post(
        "/api/auth/verify-email",
        json={"token": confirmation["token"]},
        headers=csrf_headers(current_csrf(client)),
    )

    account = await client.get("/api/account")
    assert account.json()["email"] == "new@example.com"
    assert account.json()["email_verified"] is True
    assert latest_outbox(test_settings, "email_changed")["email"] == "new@example.com"


async def test_change_password_revokes_sessions_and_requires_the_new_password(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    token = await csrf_token(client)
    await register(client, token)
    member_token = current_csrf(client)

    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": "correct horse", "new_password": "new correct horse"},
        headers=csrf_headers(member_token),
    )

    assert response.status_code == 204
    assert (await client.get("/api/me")).status_code == 401
    assert latest_outbox(test_settings, "password_changed")["username"] == "alice"

    token = await csrf_token(client)
    assert (
        await client.post(
            "/api/auth/login",
            json={"identifier": "alice", "password": "correct horse"},
            headers=csrf_headers(token),
        )
    ).status_code == 401
    token = await csrf_token(client)
    assert (
        await client.post(
            "/api/auth/login",
            json={"identifier": "alice", "password": "new correct horse"},
            headers=csrf_headers(token),
        )
    ).status_code == 200


async def test_account_export_returns_profile_and_attachment(client: AsyncClient) -> None:
    token = await csrf_token(client)
    await register(client, token)

    response = await client.get("/api/account/export")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="watchlog-export.json"'
    payload = response.json()
    assert payload["profile"]["username"] == "alice"
    assert payload["profile"]["email"] == "alice@example.com"
    assert payload["groups"] == []
    assert payload["film_scores"] == []


async def test_session_endpoint_describes_a_member(client: AsyncClient) -> None:
    token = await csrf_token(client)
    await register(client, token)

    response = await client.get("/api/auth/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "member"
    assert payload["viewer"]["name"] == "alice"
    assert payload["viewer"]["email_verified"] is False
    assert payload["email"] == "alice@example.com"
    assert payload["stats"] == {"titles_watched": 0, "average_score": None}


async def test_session_endpoint_describes_a_guest(client: AsyncClient) -> None:
    token = await csrf_token(client)
    response = await client.post(
        "/api/auth/guest",
        json={"display_name": "Riley"},
        headers=csrf_headers(token),
    )
    assert response.status_code == 201

    session = await client.get("/api/auth/session")

    assert session.status_code == 200
    payload = session.json()
    assert payload["mode"] == "guest"
    assert payload["viewer"]["name"] == "Riley"
    assert payload["viewer"]["is_guest"] is True
    assert payload["stats"] is None
    assert payload["email"] is None


async def test_unverified_accounts_cannot_create_groups(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    token = await csrf_token(client)
    await register(client, token)
    original = app.state.settings.require_verified_email
    app.state.settings.require_verified_email = True
    try:
        response = await client.post(
            "/api/groups",
            json={"name": "The club"},
            headers=csrf_headers(current_csrf(client)),
        )
    finally:
        app.state.settings.require_verified_email = original

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_unverified"
