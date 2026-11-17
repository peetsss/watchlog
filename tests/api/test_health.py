import pytest
from fastapi import FastAPI
from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.text == "ok"


async def test_health_rejects_post(client: AsyncClient) -> None:
    response = await client.post("/health")

    assert response.status_code == 405
    assert response.json() == {"error": {"code": "method_not_allowed", "message": "Method Not Allowed"}}


async def test_ready_reports_healthy_dependencies(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_probe(app: FastAPI) -> dict[str, str]:
        return {"database": "ok", "redis": "ok"}

    monkeypatch.setattr("app.api.routers.health.probe_dependencies", fake_probe)

    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok"},
    }


async def test_ready_returns_503_when_a_dependency_fails(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_probe(app: FastAPI) -> dict[str, str]:
        return {"database": "ok", "redis": "failed"}

    monkeypatch.setattr("app.api.routers.health.probe_dependencies", fake_probe)

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


async def test_security_headers_are_present(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=(), interest-cohort=()"
