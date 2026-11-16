from hmac import compare_digest
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.errors import error_payload

CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_EXEMPT_PATHS = frozenset({"/", "/health", "/ready"})


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in SAFE_METHODS or request.url.path in CSRF_EXEMPT_PATHS:
            return await call_next(request)

        settings: Settings = request.app.state.settings
        session = getattr(request.state, "session", None)
        if session is None:
            return _csrf_failure()

        header_token = request.headers.get(CSRF_HEADER_NAME, "")
        cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
        if not _tokens_match(header_token, cookie_token, session.csrf):
            return _csrf_failure()
        if not _origin_allowed(request, settings):
            return _csrf_failure()

        return await call_next(request)


def _tokens_match(header_token: str, cookie_token: str, expected: str) -> bool:
    return (
        bool(header_token)
        and bool(cookie_token)
        and compare_digest(header_token, cookie_token)
        and compare_digest(header_token, expected)
    )


def _origin_allowed(request: Request, settings: Settings) -> bool:
    origin = request.headers.get("origin")
    if origin is not None:
        return origin in settings.trusted_origins

    referer = request.headers.get("referer")
    if referer is None:
        return True

    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return False
    return f"{parsed.scheme}://{parsed.netloc}" in settings.trusted_origins


def _csrf_failure() -> JSONResponse:
    response = JSONResponse(
        error_payload("csrf_failed", "CSRF validation failed."),
        status_code=403,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
