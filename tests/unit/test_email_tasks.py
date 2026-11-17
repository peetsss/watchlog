from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.clients.resend import EmailMessage, MailError
from app.core.config import Settings
from app.models.email import EmailOutbox
from app.tasks.email import dispatch_email_outbox, send_email
from app.workers.runtime import dispose_worker_runtime, init_worker_runtime


class FakeMailer:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


def _outbox_row() -> EmailOutbox:
    return EmailOutbox(
        template="verify_email",
        recipient="alice@example.com",
        payload={
            "username": "alice",
            "public_url": "https://watchlog.example",
            "token": "token-123",
        },
        status="pending",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )


def test_send_email_marks_a_message_as_sent(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_worker_runtime(test_settings)
    mailer = FakeMailer()
    monkeypatch.setattr("app.tasks.email.build_mailer", lambda _: mailer)
    row = _outbox_row()
    sync_session.add(row)
    sync_session.commit()

    try:
        send_email.apply(args=[row.id])
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    stored = sync_session.get(EmailOutbox, row.id)
    assert stored is not None
    assert stored.status == "sent"
    assert stored.payload == {}
    assert mailer.messages[0].to == "alice@example.com"
    assert "token-123" in mailer.messages[0].text


def test_send_email_schedules_a_retry_for_transient_failures(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_worker_runtime(test_settings)

    class FailingMailer:
        def send(self, _: EmailMessage) -> None:
            raise MailError("provider unavailable", retryable=True)

    monkeypatch.setattr("app.tasks.email.build_mailer", lambda _: FailingMailer())
    row = _outbox_row()
    sync_session.add(row)
    sync_session.commit()

    try:
        send_email.apply(args=[row.id])
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    stored = sync_session.get(EmailOutbox, row.id)
    assert stored is not None
    assert stored.status == "pending"
    assert stored.attempts == 1
    assert stored.last_error == "provider unavailable"
    assert stored.next_attempt_at > datetime.now(UTC)


def test_dispatch_marks_rows_queued_and_enqueues_them(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_worker_runtime(test_settings)
    enqueued: list[int] = []
    monkeypatch.setattr("app.tasks.email.send_email.delay", lambda outbox_id: enqueued.append(outbox_id))
    row = _outbox_row()
    sync_session.add(row)
    sync_session.commit()

    try:
        count = dispatch_email_outbox.apply().get()
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    stored = sync_session.get(EmailOutbox, row.id)
    assert count == 1
    assert stored is not None
    assert stored.status == "queued"
    assert enqueued == [row.id]
