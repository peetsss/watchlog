from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_SECRET = "dev-only-change-me"
DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
DEFAULT_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost:8001",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WATCHLOG_",
        extra="ignore",
        populate_by_name=True,
    )

    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    log_level: str = "INFO"
    docs_enabled: bool = True

    secret_key: SecretStr = SecretStr(DEFAULT_SECRET)
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_HOSTS))
    trusted_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: list(DEFAULT_TRUSTED_ORIGINS))

    database_url: SecretStr | None = None
    postgres_db: str = Field("watchlog_v2", validation_alias=AliasChoices("WATCHLOG_DB", "WATCHLOG_POSTGRES_DB"))
    postgres_user: str = Field("watchlog", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(SecretStr(""), validation_alias="POSTGRES_PASSWORD")
    postgres_host: str = Field("127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, validation_alias="POSTGRES_PORT")

    redis_url: str = Field(
        "redis://127.0.0.1:6379/0",
        validation_alias=AliasChoices("WATCHLOG_REDIS_URL", "REDIS_URL"),
    )
    tmdb_api_key: SecretStr = Field(
        SecretStr(""),
        validation_alias=AliasChoices("WATCHLOG_TMDB_API_KEY", "TMDB_API_KEY"),
    )

    session_ttl_seconds: int = Field(14 * 24 * 60 * 60, gt=0)
    guest_session_ttl_seconds: int = Field(24 * 60 * 60, gt=0)
    anonymous_session_ttl_seconds: int = Field(60 * 60, gt=0)
    session_touch_interval_seconds: int = Field(60, gt=0)

    @field_validator("allowed_hosts", "trusted_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> Settings:
        if self.env != "prod":
            return self
        if self.secret_key.get_secret_value() == DEFAULT_SECRET:
            raise ValueError("WATCHLOG_SECRET_KEY must be set in production")
        if self.database_url is None and not self.postgres_password.get_secret_value():
            raise ValueError("WATCHLOG_DATABASE_URL or POSTGRES_PASSWORD must be set in production")
        return self

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password.get_secret_value())
        auth = f"{user}:{password}@" if password else f"{user}@"
        return f"postgresql+psycopg://{auth}{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def is_production(self) -> bool:
        return self.env == "prod"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @property
    def session_cookie_name(self) -> str:
        return "__Host-wl_session" if self.is_production else "wl_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "wl_csrf"


@lru_cache
def get_settings() -> Settings:
    return Settings()
