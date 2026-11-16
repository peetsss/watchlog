import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET, Settings


def test_defaults_target_the_new_database() -> None:
    settings = Settings(_env_file=None)

    assert settings.postgres_db == "watchlog_v2"
    assert settings.sqlalchemy_url == "postgresql+psycopg://watchlog@127.0.0.1:5432/watchlog_v2"


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


def test_production_accepts_explicit_configuration() -> None:
    settings = Settings(
        _env_file=None,
        env="prod",
        secret_key="a" * 32,
        database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
    )

    assert settings.is_production
