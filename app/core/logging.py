import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Literal

from app.core.redaction import RedactSecretsFilter

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_HANDLER_NAME = "watchlog"
_TEXT_LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str, log_format: Literal["text", "json"] = "text") -> None:
    root = logging.getLogger()
    formatter: logging.Formatter
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(_TEXT_LOG_FORMAT)
    for handler in root.handlers:
        if handler.get_name() == _HANDLER_NAME:
            handler.setFormatter(formatter)
            if not any(isinstance(existing, RedactSecretsFilter) for existing in handler.filters):
                handler.addFilter(RedactSecretsFilter())
            root.setLevel(level.upper())
            _quiet_http_clients()
            return
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    handler.addFilter(RedactSecretsFilter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    _quiet_http_clients()


def _quiet_http_clients() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
