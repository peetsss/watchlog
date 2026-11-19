import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.redaction import redact_path
from app.domain.lobby.errors import error_details
from app.domain.lobby.exceptions import LobbyError

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "invalid_request",
    429: "rate_limited",
}


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class RateLimitExceeded(AppError):
    code = "rate_limited"
    status_code = 429

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "Too many requests. Try again shortly.",
            code=self.code,
            status_code=self.status_code,
        )
        self.retry_after = max(retry_after, 1)


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_error(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            error_payload(exc.code, exc.message),
            status_code=exc.status_code,
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_payload(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(LobbyError)
    async def _lobby_error(request: Request, exc: LobbyError) -> JSONResponse:
        status_code, code = error_details(exc)
        return JSONResponse(error_payload(code, str(exc)), status_code=status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            error_payload("invalid_request", "The request body or parameters are invalid."),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(error_payload(code, message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error: %s %s", request.method, redact_path(request.url.path))
        return JSONResponse(
            error_payload("server_error", "An unexpected error occurred."),
            status_code=500,
        )
