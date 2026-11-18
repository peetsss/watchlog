import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var
from app.core.rate_limit import client_ip
from app.core.redaction import redact_path

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID_LENGTH = 64
_ALLOWED_REQUEST_ID_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _valid_request_id(value: str) -> bool:
    if not value or len(value) > _MAX_REQUEST_ID_LENGTH:
        return False
    return all(character in _ALLOWED_REQUEST_ID_CHARACTERS for character in value)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, "")
        if not _valid_request_id(request_id):
            request_id = uuid4().hex
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Request failed: %s %s from %s",
                request.method,
                redact_path(request.url.path),
                client_ip(request, request.app.state.settings.trusted_proxy_ips),
            )
            raise
        else:
            response.headers[REQUEST_ID_HEADER] = request_id
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "%s %s from %s -> %s (%.1f ms)",
                request.method,
                redact_path(request.url.path),
                client_ip(request, request.app.state.settings.trusted_proxy_ips),
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            request_id_var.reset(token)
