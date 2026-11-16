from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.api.routers import auth, groups, health, me, movies, root
from app.core.config import Settings, get_settings
from app.core.csrf import CSRFMiddleware
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.redis import create_redis
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.session_middleware import SessionMiddleware
from app.core.sessions import RedisSessionStore, SessionStore


def create_app(settings: Settings | None = None, session_store: SessionStore | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.engine = create_engine(resolved_settings)
        app.state.sessionmaker = create_sessionmaker(app.state.engine)
        app.state.redis = create_redis(resolved_settings)
        app.state.session_store = session_store or RedisSessionStore(app.state.redis)
        try:
            yield
        finally:
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
    app.include_router(root.router)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(movies.router)
    app.include_router(groups.router)
    return app


app = create_app()
