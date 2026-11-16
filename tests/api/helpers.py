from httpx import AsyncClient

REGISTER = {"username": "alice", "password": "correct horse"}


async def csrf_token(client: AsyncClient) -> str:
    response = await client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


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
