from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from httpx import AsyncClient

REGISTER = {"username": "alice", "password": "correct horse"}


async def csrf_token(client: AsyncClient) -> str:
    response = await client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def csrf_headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token}


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


async def test_register_me_logout_and_login(client: AsyncClient) -> None:
    token = await csrf_token(client)
    viewer = await register(client, token)

    assert viewer["mode"] == "member"
    assert viewer["username"] == "alice"
    assert viewer["initials"] == "AL"
    assert viewer["color"].startswith("#")

    member_session = client.cookies.get("wl_session")
    member_token = client.cookies.get("wl_csrf")
    assert member_session
    assert member_token
    assert member_token != token

    me = await client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["viewer"] == viewer
    assert me.json()["stats"] == {"titles_watched": 0, "average_score": None}

    logout = await client.post("/api/auth/logout", headers=csrf_headers(member_token))
    assert logout.status_code == 204
    assert client.cookies.get("wl_session") is None
    assert (await client.get("/api/me")).status_code == 401

    token = await csrf_token(client)
    login = await client.post("/api/auth/login", json=REGISTER, headers=csrf_headers(token))

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


async def test_invalid_credentials_are_rejected(client: AsyncClient) -> None:
    token = await csrf_token(client)
    response = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "wrong password"},
        headers=csrf_headers(token),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "long enough"},
        {"username": "bad name", "password": "long enough"},
        {"username": "alice", "password": "short"},
        {"username": "alice", "password": "12345678"},
        {"username": "alice", "password": "alice"},
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
