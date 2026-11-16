from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

REGISTER = {"username": "alice", "password": "correct horse"}


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
) -> dict:
    token = await csrf_token(client)
    response = await client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
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


@asynccontextmanager
async def new_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
