from pathlib import Path

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app import __version__
from app.core.config import Settings
from app.core.sessions import MemorySessionStore
from app.main import create_app
from app.realtime.hub import MemoryLobbyHub


async def test_root_describes_the_service(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "watchlog API",
        "version": __version__,
        "docs": "/api/docs",
    }


async def test_openapi_and_docs_are_available_in_dev(client: AsyncClient) -> None:
    openapi = await client.get("/api/openapi.json")
    docs = await client.get("/api/docs")

    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "watchlog API"
    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]


async def test_built_spa_is_served_when_configured(test_database: Settings, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root>watchlog</div>")
    (assets / "app.js").write_text("console.log('watchlog')")

    settings = test_database.model_copy(update={"frontend_dir": str(dist)})
    app = create_app(settings, session_store=MemorySessionStore(), hub=MemoryLobbyHub())

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            root = await client.get("/")
            deep_link = await client.get("/groups/crew")
            asset = await client.get("/assets/app.js")
            api_me = await client.get("/api/me")
            api_missing = await client.get("/api/does-not-exist")
            health = await client.get("/health")

    assert root.status_code == 200
    assert "watchlog" in root.text
    assert deep_link.status_code == 200
    assert "watchlog" in deep_link.text
    assert asset.status_code == 200
    assert "javascript" in asset.headers["content-type"]
    assert api_me.status_code == 401
    assert api_me.headers["content-type"].startswith("application/json")
    assert api_missing.status_code == 404
    assert api_missing.headers["content-type"].startswith("application/json")
    assert health.status_code == 200
    assert health.text == "ok"
