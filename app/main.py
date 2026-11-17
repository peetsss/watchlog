from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.api.routers import account, auth, group_invites, groups, health, home, lobby, me, movies, root
from app.core.config import Settings, get_settings
from app.core.csrf import CSRFMiddleware
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.observability import init_sentry
from app.core.rate_limit import MemoryRateLimiter, RedisRateLimiter
from app.core.redis import create_redis
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.session_middleware import SessionMiddleware
from app.core.sessions import RedisSessionStore, SessionStore
from app.realtime.hub import LobbyHub, RedisLobbyHub
from app.realtime.ws_lobby import router as lobby_ws_router


def create_app(
    settings: Settings | None = None,
    session_store: SessionStore | None = None,
    hub: LobbyHub | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level, resolved_settings.log_format)
    init_sentry(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.engine = create_engine(resolved_settings)
        app.state.sessionmaker = create_sessionmaker(app.state.engine)
        app.state.redis = create_redis(resolved_settings)
        app.state.session_store = session_store or RedisSessionStore(app.state.redis)
        app.state.rate_limiter = (
            MemoryRateLimiter() if resolved_settings.env == "test" else RedisRateLimiter(app.state.redis)
        )
        app.state.hub = hub or RedisLobbyHub(app.state.redis)
        await app.state.hub.start()
        try:
            yield
        finally:
            await app.state.hub.stop()
            await app.state.redis.aclose()
            await app.state.engine.dispose()

    app = FastAPI(
        title="watchlog API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if resolved_settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if resolved_settings.docs_enabled else None,
    )

    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SessionMiddleware)
    if resolved_settings.env != "test":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved_settings.allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(account.router)
    app.include_router(me.router)
    app.include_router(movies.router)
    app.include_router(groups.router)
    app.include_router(group_invites.router)
    app.include_router(home.router)
    app.include_router(lobby.router)
    app.include_router(lobby_ws_router)

    frontend_dir = Path(resolved_settings.frontend_dir) if resolved_settings.frontend_dir else None
    if frontend_dir is not None and (frontend_dir / "index.html").is_file():
        assets_dir = frontend_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        async def frontend_root() -> FileResponse:
            return FileResponse(frontend_dir / "index.html", headers={"Cache-Control": "no-cache"})

        @app.get("/{full_path:path}", include_in_schema=False)
        async def frontend_spa(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith(("api/", "ws/", "health", "ready")):
                raise HTTPException(status_code=404)
            candidate = (frontend_dir / full_path).resolve()
            if full_path and candidate.is_relative_to(frontend_dir.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dir / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        app.include_router(root.router)

    return app


app = create_app()
