import warnings
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
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    docs_enabled: bool = False
    public_url: str | None = None

    secret_key: SecretStr = SecretStr(DEFAULT_SECRET)
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_HOSTS))
    trusted_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: list(DEFAULT_TRUSTED_ORIGINS))
    trusted_proxy_ips: Annotated[list[str], NoDecode] = Field(default_factory=list)

    database_url: SecretStr | None = None
    postgres_db: str = Field(
        "watchlog_v2",
        validation_alias=AliasChoices("WATCHLOG_DB", "WATCHLOG_POSTGRES_DB", "POSTGRES_DB"),
    )
    postgres_user: str = Field("watchlog", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(SecretStr(""), validation_alias="POSTGRES_PASSWORD")
    postgres_host: str = Field("127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, validation_alias="POSTGRES_PORT")

    redis_url: str = Field(
        "redis://127.0.0.1:6379/0",
        validation_alias=AliasChoices("WATCHLOG_REDIS_URL", "REDIS_URL"),
    )
    celery_broker_url: str = Field(
        "redis://127.0.0.1:6379/1",
        validation_alias=AliasChoices("WATCHLOG_CELERY_BROKER_URL", "CELERY_BROKER_URL"),
    )
    tmdb_api_key: SecretStr = Field(
        SecretStr(""),
        validation_alias=AliasChoices("WATCHLOG_TMDB_API_KEY", "TMDB_API_KEY"),
    )
    tmdb_access_token: SecretStr = Field(
        SecretStr(""),
        validation_alias=AliasChoices("WATCHLOG_TMDB_ACCESS_TOKEN", "TMDB_ACCESS_TOKEN"),
    )
    tmdb_language: str = "en-US"
    tmdb_rate_limit_per_second: float = Field(10.0, gt=0)
    tmdb_sync_lookback_days: int = Field(7, gt=0)
    tmdb_sync_max_pages: int = Field(25, ge=1)
    default_region: str = "PL"
    supported_regions: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["PL"])
    watch_provider_ttl_seconds: int = Field(24 * 60 * 60, gt=0)
    provider_refresh_limit: int = Field(500, ge=1)

    mail_backend: Literal["console", "resend"] = "console"
    mail_from: str = ""
    mail_reply_to: str = ""
    resend_api_key: SecretStr = SecretStr("")

    sentry_dsn: SecretStr = SecretStr("")
    rate_limit_enabled: bool = True
    require_verified_email: bool = True
    legacy_group_join_enabled: bool = False

    frontend_dir: str | None = None

    session_ttl_seconds: int = Field(14 * 24 * 60 * 60, gt=0)
    guest_session_ttl_seconds: int = Field(24 * 60 * 60, gt=0)
    anonymous_session_ttl_seconds: int = Field(60 * 60, gt=0)
    session_touch_interval_seconds: int = Field(60, gt=0)
    max_request_body_bytes: int = Field(1_048_576, ge=1024, le=16_777_216)

    @field_validator("allowed_hosts", "trusted_origins", "trusted_proxy_ips", "supported_regions", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("public_url")
    @classmethod
    def normalize_public_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @field_validator("default_region", "supported_regions")
    @classmethod
    def validate_region_codes(cls, value: str | list[str]) -> str | list[str]:
        regions = [value] if isinstance(value, str) else value
        if not regions:
            raise ValueError("At least one supported region is required")
        for region in regions:
            if len(region) != 2 or not region.isalpha() or region.upper() != region:
                raise ValueError("Region codes must be two uppercase letters")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> Settings:
        if self.default_region not in self.supported_regions:
            raise ValueError("WATCHLOG_DEFAULT_REGION must be in WATCHLOG_SUPPORTED_REGIONS")
        if self.env != "prod":
            return self
        if self.secret_key.get_secret_value() == DEFAULT_SECRET:
            raise ValueError("WATCHLOG_SECRET_KEY must be set in production")
        if self.database_url is None and not self.postgres_password.get_secret_value():
            raise ValueError("WATCHLOG_DATABASE_URL or POSTGRES_PASSWORD must be set in production")
        if not self.public_url:
            raise ValueError("WATCHLOG_PUBLIC_URL must be set in production")
        if not self.public_url.startswith("https://"):
            raise ValueError("WATCHLOG_PUBLIC_URL must use https in production")
        if self.docs_enabled:
            raise ValueError("WATCHLOG_DOCS_ENABLED must be false in production")
        if self.allowed_hosts == DEFAULT_ALLOWED_HOSTS:
            raise ValueError("WATCHLOG_ALLOWED_HOSTS must be set for the production host")
        if self.trusted_origins == DEFAULT_TRUSTED_ORIGINS:
            raise ValueError("WATCHLOG_TRUSTED_ORIGINS must be set for the production origin")
        if not self.trusted_proxy_ips:
            warnings.warn(
                "WATCHLOG_TRUSTED_PROXY_IPS is empty; X-Forwarded-For is ignored",
                UserWarning,
                stacklevel=2,
            )
        if self.mail_backend != "resend":
            raise ValueError("WATCHLOG_MAIL_BACKEND must be resend in production")
        if not self.mail_from:
            raise ValueError("WATCHLOG_MAIL_FROM must be set when WATCHLOG_MAIL_BACKEND=resend")
        if not self.resend_api_key.get_secret_value():
            raise ValueError("WATCHLOG_RESEND_API_KEY must be set when WATCHLOG_MAIL_BACKEND=resend")
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
