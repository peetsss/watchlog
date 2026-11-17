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
