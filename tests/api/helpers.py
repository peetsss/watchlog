from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

REGISTER = {"username": "alice", "email": "alice@example.com", "password": "correct horse"}


async def csrf_token(client: AsyncClient) -> str:
    response = await client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def current_csrf(client: AsyncClient) -> str:
    token = client.cookies.get("wl_csrf")
    assert token
    return token


def csrf_headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token}


async def register_member(
    client: AsyncClient,
    username: str = "alice",
    password: str = "correct horse",
    email: str | None = None,
) -> dict:
    token = await csrf_token(client)
    response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
        headers=csrf_headers(token),
    )
    assert response.status_code == 201
    return response.json()["viewer"]


async def create_group(client: AsyncClient, name: str, description: str | None = None) -> dict:
    payload: dict[str, object] = {"name": name}
    if description is not None:
        payload["description"] = description
    response = await client.post("/api/groups", json=payload, headers=csrf_headers(current_csrf(client)))
    assert response.status_code == 201
    return response.json()


async def join_group(client: AsyncClient, group_id: str) -> dict:
    response = await client.post(
        f"/api/groups/{group_id}/members",
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 200
    return response.json()


async def add_film(client: AsyncClient, group_id: str, tmdb_id: int, media_type: str = "movie") -> dict:
    response = await client.post(
        f"/api/groups/{group_id}/films",
        json={"tmdb_id": tmdb_id, "media_type": media_type},
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 200
    return response.json()


async def score_film(client: AsyncClient, group_id: str, film_id: int, score: float) -> dict:
    response = await client.put(
        f"/api/groups/{group_id}/films/{film_id}/score",
        json={"score": score},
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 200
    return response.json()


async def set_film_status(client: AsyncClient, group_id: str, film_id: int, status: str) -> dict:
    response = await client.patch(
        f"/api/groups/{group_id}/films/{film_id}",
        json={"status": status},
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 200
    return response.json()


async def create_group_lobby(client: AsyncClient, group_id: str) -> dict:
    response = await client.post(
        f"/api/groups/{group_id}/lobbies",
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 201
    return response.json()["lobby"]


async def create_lobby(client: AsyncClient, group_uuid: str | None = None) -> dict:
    payload: dict[str, object] = {} if group_uuid is None else {"group_uuid": group_uuid}
    response = await client.post("/api/lobby/", json=payload, headers=csrf_headers(current_csrf(client)))
    assert response.status_code == 201
    return response.json()["lobby"]


async def join_open_lobby(client: AsyncClient, lobby_id: str) -> dict:
    response = await client.post(
        f"/api/lobby/{lobby_id}/join/",
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 200
    return response.json()["lobby"]


async def lobby_action(
    client: AsyncClient,
    lobby_id: str,
    action: str,
    payload: dict[str, object] | None = None,
) -> dict:
    response = await client.post(
        f"/api/lobby/{lobby_id}/{action}/",
        json=payload or {},
        headers=csrf_headers(current_csrf(client)),
    )
    assert response.status_code == 200
    return response.json()["lobby"]


async def lobby_state(client: AsyncClient, lobby_id: str) -> dict:
    response = await client.get(f"/api/lobby/{lobby_id}/")
    assert response.status_code == 200
    return response.json()["lobby"]


@asynccontextmanager
async def new_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
