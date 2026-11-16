import logging
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.core.sessions import SessionData, SessionStore, ttl_for

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings: Settings = request.app.state.settings
        store: SessionStore = request.app.state.session_store
        request.state.session = None
        request.state.session_id = None

        session_id = request.cookies.get(settings.session_cookie_name)
        if session_id:
            try:
                data = await store.get(session_id)
            except Exception:
                logger.warning("Failed to load the session", exc_info=True)
                data = None
            if data is not None:
                request.state.session = data
                request.state.session_id = session_id
                await self._refresh(request, store, session_id, data, settings)

        return await call_next(request)

    async def _refresh(
        self,
        request: Request,
        store: SessionStore,
        session_id: str,
        data: SessionData,
        settings: Settings,
    ) -> None:
        ttl = ttl_for(data.kind, settings)
        try:
            now = datetime.now(UTC)
            if (now - data.last_seen).total_seconds() >= settings.session_touch_interval_seconds:
                refreshed = data.model_copy(update={"last_seen": now})
                await store.save(session_id, refreshed, ttl)
                request.state.session = refreshed
            else:
                await store.touch(session_id, ttl)
        except Exception:
            logger.warning("Failed to refresh the session", exc_info=True)
