import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_ALLOWED_HOSTS, DEFAULT_SECRET, DEFAULT_TRUSTED_ORIGINS, Settings

POSTGRES_ENV_VARS = (
    "WATCHLOG_DB",
    "WATCHLOG_POSTGRES_DB",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "WATCHLOG_DATABASE_URL",
)


@pytest.fixture(autouse=True)
def _clean_database_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in POSTGRES_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_target_the_new_database() -> None:
    settings = Settings(_env_file=None)

    assert settings.postgres_db == "watchlog_v2"
    assert settings.sqlalchemy_url == "postgresql+psycopg://watchlog@127.0.0.1:5432/watchlog_v2"
    assert settings.tmdb_language == "en-US"
    assert settings.default_region == "PL"
    assert settings.supported_regions == ["PL"]
    assert settings.celery_broker_url == "redis://127.0.0.1:6379/1"
    assert settings.max_request_body_bytes == 1_048_576
    assert settings.docs_enabled is False


def test_database_url_override_wins() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
    )

    assert settings.sqlalchemy_url == "postgresql+psycopg://user:secret@db.example:5432/watchlog"


def test_environment_overrides_use_the_new_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WATCHLOG_DB", "watchlog_custom")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:word")

    settings = Settings(_env_file=None)

    assert settings.postgres_db == "watchlog_custom"
    assert settings.postgres_password.get_secret_value() == "p@ss:word"
    assert settings.sqlalchemy_url == "postgresql+psycopg://watchlog:p%40ss%3Aword@127.0.0.1:5432/watchlog_custom"


def test_comma_separated_lists_are_split() -> None:
    settings = Settings(
        _env_file=None,
        allowed_hosts="localhost,api,127.0.0.1",
        trusted_origins="http://localhost:5173, http://localhost:8001",
    )

    assert settings.allowed_hosts == ["localhost", "api", "127.0.0.1"]
    assert settings.trusted_origins == ["http://localhost:5173", "http://localhost:8001"]


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "prod",
        "secret_key": "a" * 32,
        "public_url": "https://watchlog.example",
        "database_url": "postgresql+psycopg://user:secret@db.example:5432/watchlog",
        "allowed_hosts": "watchlog.example",
        "trusted_origins": "https://watchlog.example",
        "trusted_proxy_ips": "172.18.0.0/16",
        "docs_enabled": False,
        "mail_backend": "resend",
        "mail_from": "watchlog <hello@watchlog.example>",
        "resend_api_key": "re_test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_requires_a_real_secret() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_SECRET_KEY"):
        production_settings(secret_key=DEFAULT_SECRET)


def test_production_rejects_the_default_secret_even_with_a_database() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_SECRET_KEY"):
        production_settings(secret_key=DEFAULT_SECRET)


def test_production_requires_a_public_url() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_PUBLIC_URL"):
        production_settings(public_url=None)


def test_production_rejects_http_public_url() -> None:
    with pytest.raises(ValidationError, match="must use https"):
        production_settings(public_url="http://watchlog.example")


def test_production_rejects_docs_enabled() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_DOCS_ENABLED"):
        production_settings(docs_enabled=True)


def test_production_rejects_default_hosts() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_ALLOWED_HOSTS"):
        production_settings(allowed_hosts=DEFAULT_ALLOWED_HOSTS)


def test_production_rejects_default_origins() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_TRUSTED_ORIGINS"):
        production_settings(trusted_origins=DEFAULT_TRUSTED_ORIGINS)


def test_production_warns_when_trusted_proxies_are_empty() -> None:
    with pytest.warns(UserWarning, match="TRUSTED_PROXY_IPS"):
        production_settings(trusted_proxy_ips=[])


def test_production_requires_resend_configuration_when_using_resend() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_MAIL_FROM"):
        production_settings(mail_from="")


def test_production_accepts_explicit_configuration() -> None:
    settings = production_settings(public_url="https://watchlog.example/")

    assert settings.is_production
    assert settings.public_url == "https://watchlog.example"


def test_production_rejects_the_console_mailer() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_MAIL_BACKEND must be resend"):
        production_settings(mail_backend="console")


def test_region_configuration_is_validated() -> None:
    with pytest.raises(ValidationError, match="two uppercase letters"):
        Settings(_env_file=None, default_region="pl")

    with pytest.raises(ValidationError, match="WATCHLOG_DEFAULT_REGION"):
        Settings(_env_file=None, default_region="US", supported_regions="PL")

    settings = Settings(_env_file=None, supported_regions="PL,DE", default_region="PL")
    assert settings.supported_regions == ["PL", "DE"]
