import json

import httpx
import pytest

from app.clients.resend import EmailMessage, MailError, ResendMailer, build_mailer
from app.core.config import Settings
from app.services.mail import render_email


def test_verify_email_renders_both_formats() -> None:
    subject, html, text = render_email(
        "verify_email",
        {
            "username": "alice",
            "public_url": "https://watchlog.example",
            "token": "token-123",
        },
    )

    assert subject == "Confirm your watchlog email"
    assert "https://watchlog.example/verify-email?token=token-123" in html
    assert "https://watchlog.example/verify-email?token=token-123" in text
    assert "alice" in text


def test_unknown_email_template_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown email template"):
        render_email("missing", {})


def test_resend_mailer_posts_an_email() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "email_123"})

    mailer = ResendMailer(
        api_key="re_test",
        sender="watchlog <hello@watchlog.example>",
        reply_to="support@watchlog.example",
        transport=httpx.MockTransport(handler),
    )

    mailer.send(
        EmailMessage(
            to="alice@example.com",
            subject="Hello",
            html="<p>Hello</p>",
            text="Hello",
        )
    )

    request = captured[0]
    payload = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer re_test"
    assert payload["from"] == "watchlog <hello@watchlog.example>"
    assert payload["to"] == ["alice@example.com"]
    assert payload["reply_to"] == "support@watchlog.example"


def test_resend_mailer_marks_server_errors_as_retryable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    mailer = ResendMailer(
        api_key="re_test",
        sender="hello@watchlog.example",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(MailError) as exc_info:
        mailer.send(EmailMessage(to="alice@example.com", subject="Hello", html="", text=""))

    assert exc_info.value.retryable is True


def test_resend_mailer_marks_client_errors_as_permanent() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(422)

    mailer = ResendMailer(
        api_key="re_test",
        sender="hello@watchlog.example",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(MailError) as exc_info:
        mailer.send(EmailMessage(to="alice@example.com", subject="Hello", html="", text=""))

    assert exc_info.value.retryable is False


def test_build_mailer_uses_the_console_backend_by_default() -> None:
    mailer = build_mailer(Settings(_env_file=None))

    assert mailer.__class__.__name__ == "ConsoleMailer"
