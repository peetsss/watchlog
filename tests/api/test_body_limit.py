import logging

from httpx import AsyncClient


async def test_small_request_is_allowed(client: AsyncClient) -> None:
    response = await client.get("/api/auth/csrf")

    assert response.status_code == 200


async def test_oversized_body_is_rejected_before_parsing(client: AsyncClient, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.core.middleware")
    body = b"x" * (1_048_576 + 1)

    response = await client.post(
        "/api/auth/register",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
    assert "/api/auth/register" in caplog.text
