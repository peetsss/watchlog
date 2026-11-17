import json
import logging

from app.core.logging import JsonFormatter, RequestIdFilter, request_id_var


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
