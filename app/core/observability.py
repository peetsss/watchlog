import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app import __version__
from app.core.config import Settings
from app.core.redaction import redact_text

_SENSITIVE_NAMES = ("authorization", "cookie", "token", "key", "secret", "password")


def _sensitive(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in _SENSITIVE_NAMES)


def _scrub_headers(headers: object) -> object:
    if isinstance(headers, dict):
        return {
            name: "[REDACTED]" if _sensitive(str(name)) else redact_text(value) if isinstance(value, str) else value
            for name, value in headers.items()
        }
    if isinstance(headers, list):
        scrubbed: list[object] = []
        for item in headers:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                name, value = item
                scrubbed.append(
                    (
                        name,
                        "[REDACTED]"
                        if _sensitive(str(name))
                        else redact_text(value)
                        if isinstance(value, str)
                        else value,
                    )
                )
            else:
                scrubbed.append(item)
        return scrubbed
    return headers


def _scrub_event(event: dict[str, object], hint: dict[str, object]) -> dict[str, object]:
    try:
        request = event.get("request")
        if isinstance(request, dict):
            request.pop("data", None)
            request.pop("cookies", None)
            query_string = request.get("query_string")
            if isinstance(query_string, str):
                request["query_string"] = redact_text(query_string)
            headers = request.get("headers")
            if headers:
                request["headers"] = _scrub_headers(headers)
    except Exception:
        pass
    return event


def _scrub_breadcrumb(crumb: dict[str, object], hint: dict[str, object]) -> dict[str, object]:
    try:
        message = crumb.get("message")
        if isinstance(message, str):
            crumb["message"] = redact_text(message)
        data = crumb.get("data")
        if isinstance(data, dict):
            crumb["data"] = {
                key: redact_text(value) if isinstance(value, str) else value for key, value in data.items()
            }
    except Exception:
        pass
    return crumb


def init_sentry(settings: Settings) -> None:
    dsn = settings.sentry_dsn.get_secret_value()
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.env,
        release=__version__,
        send_default_pii=False,
        max_request_body_size="never",
        before_send=_scrub_event,
        before_breadcrumb=_scrub_breadcrumb,
        traces_sample_rate=0.0,
        integrations=[FastApiIntegration(), CeleryIntegration()],
    )
