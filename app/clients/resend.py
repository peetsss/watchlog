import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

RESEND_BASE_URL = "https://api.resend.com"


class MailError(Exception):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str
    reply_to: str | None = None


class Mailer(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleMailer:
    def send(self, message: EmailMessage) -> None:
        logger.info("dev email to %s: %s\n%s", message.to, message.subject, message.text)


class ResendMailer:
    def __init__(
        self,
        api_key: str,
        sender: str,
        reply_to: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._sender = sender
        self._reply_to = reply_to
        self._timeout = timeout
        self._transport = transport

    def send(self, message: EmailMessage) -> None:
        payload: dict[str, object] = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if self._reply_to:
            payload["reply_to"] = self._reply_to
        try:
            with httpx.Client(base_url=RESEND_BASE_URL, timeout=self._timeout, transport=self._transport) as client:
                response = client.post(
                    "/emails",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx.HTTPError as exc:
            raise MailError("The mail provider could not be reached.", retryable=True) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise MailError(
                f"The mail provider returned {response.status_code}.",
                retryable=True,
            )
        if response.status_code >= 400:
            raise MailError(
                f"The mail provider rejected the message with {response.status_code}.",
                retryable=False,
            )


def build_mailer(settings: Settings) -> Mailer:
    if settings.mail_backend == "console":
        return ConsoleMailer()
    api_key = settings.resend_api_key.get_secret_value()
    if not api_key or not settings.mail_from:
        raise RuntimeError("Resend mail is enabled without an API key or sender")
    return ResendMailer(
        api_key=api_key,
        sender=settings.mail_from,
        reply_to=settings.mail_reply_to or None,
    )
