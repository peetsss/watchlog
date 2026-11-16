from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.sessions import MemorySessionStore
from app.main import create_app
from app.realtime.hub import MemoryLobbyHub


async def test_unknown_route_uses_the_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


async def test_request_id_is_echoed_when_valid(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.headers["X-Request-ID"] == "request-123"


async def test_invalid_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "not a valid id"})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "not a valid id"
    assert len(request_id) == 32


async def test_unhandled_errors_use_the_error_envelope() -> None:
    app = create_app(
        Settings(env="test", docs_enabled=True, _env_file=None),
        session_store=MemorySessionStore(),
        hub=MemoryLobbyHub(),
    )

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    async with LifespanManager(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "server_error", "message": "An unexpected error occurred."}}
