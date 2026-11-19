import json
import logging

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

_ERROR_BODY = json.dumps({"error": {"code": "request_too_large", "message": "Request body is too large."}}).encode(
    "utf-8"
)


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > self.max_bytes:
                await self._reject(send)
                return

        total = 0
        capped = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal total, capped
            message = await receive()
            if message["type"] != "http.request":
                return message
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                if not capped:
                    logger.warning("Request body exceeded the %s byte limit", self.max_bytes)
                    capped = True
                if response_started:
                    return message
                return {"type": "http.disconnect"}
            return message

        async def limited_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self.app(scope, limited_receive, limited_send)

    async def _reject(self, send: Send) -> None:
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(_ERROR_BODY)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": _ERROR_BODY})
