import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET, Settings

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


def test_production_requires_a_real_secret() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_SECRET_KEY"):
        Settings(
            _env_file=None,
            env="prod",
            database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
        )


def test_production_rejects_the_default_secret_even_with_a_database() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_SECRET_KEY"):
        Settings(
            _env_file=None,
            env="prod",
            secret_key=DEFAULT_SECRET,
            database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
        )


def test_production_requires_a_public_url() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_PUBLIC_URL"):
        Settings(
            _env_file=None,
            env="prod",
            secret_key="a" * 32,
            database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
        )


def test_production_requires_resend_configuration_when_using_resend() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_MAIL_FROM"):
        Settings(
            _env_file=None,
            env="prod",
            secret_key="a" * 32,
            public_url="https://watchlog.example",
            database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
            mail_backend="resend",
        )


def test_production_accepts_explicit_configuration() -> None:
    settings = Settings(
        _env_file=None,
        env="prod",
        secret_key="a" * 32,
        public_url="https://watchlog.example/",
        database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
        mail_backend="resend",
        mail_from="watchlog <hello@watchlog.example>",
        resend_api_key="re_test",
    )

    assert settings.is_production
    assert settings.public_url == "https://watchlog.example"


def test_production_rejects_the_console_mailer() -> None:
    with pytest.raises(ValidationError, match="WATCHLOG_MAIL_BACKEND must be resend"):
        Settings(
            _env_file=None,
            env="prod",
            secret_key="a" * 32,
            public_url="https://watchlog.example",
            database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
            mail_backend="console",
        )


def test_region_configuration_is_validated() -> None:
    with pytest.raises(ValidationError, match="two uppercase letters"):
        Settings(_env_file=None, default_region="pl")

    with pytest.raises(ValidationError, match="WATCHLOG_DEFAULT_REGION"):
        Settings(_env_file=None, default_region="US", supported_regions="PL")

    settings = Settings(_env_file=None, supported_regions="PL,DE", default_region="PL")
    assert settings.supported_regions == ["PL", "DE"]
