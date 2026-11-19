import json
import logging

from app.core.logging import JsonFormatter, RequestIdFilter, configure_logging, request_id_var
from app.core.redaction import RedactSecretsFilter


def test_json_formatter_includes_request_id() -> None:
    record = logging.LogRecord(
        name="watchlog.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="processed %s",
        args=("items",),
        exc_info=None,
    )
    token = request_id_var.set("request-123")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "watchlog.test"
    assert payload["message"] == "processed items"
    assert payload["request_id"] == "request-123"


def test_configure_logging_installs_redaction_and_quiets_http_clients() -> None:
    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    previous = (httpx_logger.level, httpcore_logger.level)
    try:
        configure_logging("DEBUG")

        handler = next(handler for handler in logging.getLogger().handlers if handler.get_name() == "watchlog")
        assert any(isinstance(filter_, RedactSecretsFilter) for filter_ in handler.filters)
        assert httpx_logger.level == logging.WARNING
        assert httpcore_logger.level == logging.WARNING
    finally:
        httpx_logger.setLevel(previous[0])
        httpcore_logger.setLevel(previous[1])
