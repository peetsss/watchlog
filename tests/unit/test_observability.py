import pytest

from app.core.config import Settings
from app.core.observability import init_sentry


def test_init_sentry_is_a_noop_without_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kwargs: calls.append(kwargs))

    init_sentry(Settings(_env_file=None))

    assert calls == []


def test_init_sentry_passes_the_configured_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kwargs: calls.append(kwargs))

    init_sentry(Settings(_env_file=None, env="test", sentry_dsn="https://public@sentry.example/1"))

    assert calls[0]["dsn"] == "https://public@sentry.example/1"
    assert calls[0]["environment"] == "test"
    assert calls[0]["send_default_pii"] is False
    assert calls[0]["max_request_body_size"] == "never"


def test_scrub_event_removes_bodies_cookies_and_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kwargs: calls.append(kwargs))
    init_sentry(Settings(_env_file=None, env="test", sentry_dsn="https://public@sentry.example/1"))

    scrub = calls[0]["before_send"]
    event = {
        "request": {
            "data": {"password": "secret"},
            "cookies": {"session": "secret"},
            "query_string": "token=query-secret",
            "headers": {
                "Authorization": "Bearer bearer-secret",
                "X-Test": "token=header-secret",
                "Accept": "application/json",
            },
        }
    }

    scrubbed = scrub(event, {})

    assert "data" not in scrubbed["request"]
    assert "cookies" not in scrubbed["request"]
    assert "query-secret" not in str(scrubbed)
    assert "bearer-secret" not in str(scrubbed)
    assert "header-secret" not in str(scrubbed)
    assert scrubbed["request"]["headers"]["Accept"] == "application/json"


def test_scrub_breadcrumb_redacts_invite_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kwargs: calls.append(kwargs))
    init_sentry(Settings(_env_file=None, env="test", sentry_dsn="https://public@sentry.example/1"))

    scrub = calls[0]["before_breadcrumb"]
    crumb = {"message": "GET /join/group/invite-secret", "data": {"url": "/api/group-invites/other-secret"}}

    scrubbed = scrub(crumb, {})

    assert "invite-secret" not in str(scrubbed)
    assert "other-secret" not in str(scrubbed)
    assert "[REDACTED]" in scrubbed["message"]


def test_scrubber_never_raises_on_unexpected_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.observability.sentry_sdk.init", lambda **kwargs: calls.append(kwargs))
    init_sentry(Settings(_env_file=None, env="test", sentry_dsn="https://public@sentry.example/1"))

    event = {"request": "unexpected"}
    assert calls[0]["before_send"](event, {}) is event
