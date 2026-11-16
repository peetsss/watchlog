from starlette.requests import Request

from app.core.config import Settings
from app.core.csrf import _origin_allowed, _tokens_match


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/test",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }
    return Request(scope)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        trusted_origins=["http://localhost:8001"],
    )


def test_tokens_must_match_each_other_and_the_session() -> None:
    assert _tokens_match("token", "token", "token")
    assert not _tokens_match("", "token", "token")
    assert not _tokens_match("token", "", "token")
    assert not _tokens_match("token", "other", "token")
    assert not _tokens_match("token", "token", "other")


def test_allowed_origin() -> None:
    request = _request({"origin": "http://localhost:8001"})

    assert _origin_allowed(request, _settings())


def test_disallowed_origin() -> None:
    request = _request({"origin": "http://evil.example"})

    assert not _origin_allowed(request, _settings())


def test_allowed_referer_when_origin_is_missing() -> None:
    request = _request({"referer": "http://localhost:8001/some/page"})

    assert _origin_allowed(request, _settings())


def test_disallowed_referer() -> None:
    request = _request({"referer": "http://evil.example/some/page"})

    assert not _origin_allowed(request, _settings())


def test_missing_origin_and_referer_is_allowed_after_token_check() -> None:
    request = _request({})

    assert _origin_allowed(request, _settings())
