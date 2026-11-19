import logging

from app.core.redaction import RedactSecretsFilter, redact_path, redact_text


def test_redacts_query_tokens() -> None:
    text = "GET /reset?token=verify-secret&api_key=tmdb-secret&access_token=v4-secret&csrf=csrf-secret&password=pw"

    redacted = redact_text(text)

    assert "verify-secret" not in redacted
    assert "tmdb-secret" not in redacted
    assert "v4-secret" not in redacted
    assert "csrf-secret" not in redacted
    assert "pw" not in redacted
    assert redacted.count("[REDACTED]") == 5


def test_redacts_invite_paths() -> None:
    assert redact_text("/api/group-invites/invite-secret") == "/api/group-invites/[REDACTED]"
    assert redact_text("/join/group/join-secret") == "/join/group/[REDACTED]"


def test_redacts_bearer_tokens() -> None:
    assert redact_text("Authorization: Bearer abc.def-123") == "Authorization: Bearer [REDACTED]"


def test_ordinary_paths_are_unchanged() -> None:
    assert redact_text("/api/groups/123/watchlist") == "/api/groups/123/watchlist"


def test_redact_path_removes_control_characters() -> None:
    redacted = redact_path("/join/group/secret\nnext\x1b")

    assert "secret" not in redacted
    assert "\n" not in redacted
    assert "\x1b" not in redacted
    assert "[REDACTED]" in redacted


def test_filter_redacts_formatted_arguments() -> None:
    record = logging.LogRecord(
        name="watchlog.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET /reset?token=%s",
        args=("secret-token",),
        exc_info=None,
    )

    assert RedactSecretsFilter().filter(record) is True
    assert "secret-token" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()
