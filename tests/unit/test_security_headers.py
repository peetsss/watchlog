from app.core.config import Settings
from app.core.security_headers import content_security_policy


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        env="prod",
        secret_key="a" * 32,
        public_url="https://watchlog.example",
        database_url="postgresql+psycopg://user:secret@db.example:5432/watchlog",
        allowed_hosts="watchlog.example",
        trusted_origins="https://watchlog.example",
        trusted_proxy_ips="172.18.0.0/16",
        docs_enabled=False,
        mail_backend="resend",
        mail_from="watchlog <hello@watchlog.example>",
        resend_api_key="re_test",
    )


def test_development_csp_allows_live_reload_websockets() -> None:
    policy = content_security_policy(Settings(_env_file=None))

    assert "connect-src 'self' ws: wss:" in policy


def test_production_csp_only_allows_the_public_websocket_host() -> None:
    policy = content_security_policy(production_settings())

    assert "connect-src 'self' wss://watchlog.example" in policy
    assert " ws: " not in policy
