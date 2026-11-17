import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery_app
from app.clients.resend import EmailMessage, MailError, build_mailer
from app.core.config import get_settings
from app.models.email import EmailOutbox, EmailToken
from app.services.mail import render_email
from app.workers.runtime import get_worker_runtime

logger = logging.getLogger(__name__)

DISPATCH_BATCH_SIZE = 20
MAX_SEND_ATTEMPTS = 8
SENDING_LEASE_SECONDS = 5 * 60
TOKEN_RETENTION_DAYS = 7
OUTBOX_RETENTION_DAYS = 30


def _now() -> datetime:
    return datetime.now(UTC)


def _retry_delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * (2 ** max(attempts - 1, 0)), 3600))


@celery_app.task(name="watchlog.email.dispatch_outbox")
def dispatch_email_outbox() -> int:
    sessionmaker = get_worker_runtime().sessionmaker
    now = _now()
    outbox_ids: list[int] = []
    with sessionmaker() as session:
        rows = list(
            session.scalars(
                select(EmailOutbox)
                .where(
                    EmailOutbox.status.in_(("pending", "sending")),
                    EmailOutbox.next_attempt_at <= now,
                )
                .order_by(EmailOutbox.id)
                .limit(DISPATCH_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            row.status = "queued"
            outbox_ids.append(row.id)
        session.commit()

    for outbox_id in outbox_ids:
        try:
            send_email.delay(outbox_id)
        except Exception:
            logger.exception("Failed to enqueue email outbox row %s", outbox_id)
            with sessionmaker() as session:
                row = session.get(EmailOutbox, outbox_id)
                if row is not None and row.status == "queued":
                    row.status = "pending"
                    row.next_attempt_at = now + timedelta(seconds=30)
                    session.commit()
    return len(outbox_ids)


@celery_app.task(name="watchlog.email.send")
def send_email(outbox_id: int) -> None:
    sessionmaker = get_worker_runtime().sessionmaker
    settings = get_settings()
    now = _now()
    with sessionmaker() as session:
        row = session.scalar(select(EmailOutbox).where(EmailOutbox.id == outbox_id).with_for_update())
        if row is None or row.status in {"sent", "failed"}:
            return
        if row.status == "sending" and row.next_attempt_at > now:
            return
        row.status = "sending"
        row.attempts += 1
        row.next_attempt_at = now + timedelta(seconds=SENDING_LEASE_SECONDS)
        payload = dict(row.payload)
        template = row.template
        recipient = row.recipient
        attempts = row.attempts
        session.commit()

    try:
        subject, html, text = render_email(template, payload)
        mailer = build_mailer(settings)
        mailer.send(EmailMessage(to=recipient, subject=subject, html=html, text=text))
    except MailError as exc:
        logger.exception("Email outbox row %s failed", outbox_id)
        _mark_failed_or_retry(sessionmaker, outbox_id, attempts, str(exc), retryable=exc.retryable)
        return
    except Exception as exc:
        logger.exception("Email outbox row %s could not be rendered or sent", outbox_id)
        _mark_failed_or_retry(sessionmaker, outbox_id, attempts, str(exc), retryable=True)
        return

    with sessionmaker() as session:
        row = session.get(EmailOutbox, outbox_id)
        if row is not None:
            row.status = "sent"
            row.sent_at = _now()
            row.payload = {}
            row.last_error = None
            session.commit()


def _mark_failed_or_retry(
    session_factory: sessionmaker[Session],
    outbox_id: int,
    attempts: int,
    error: str,
    *,
    retryable: bool,
) -> None:
    with session_factory() as session:
        row = session.get(EmailOutbox, outbox_id)
        if row is None:
            return
        if not retryable or attempts >= MAX_SEND_ATTEMPTS:
            row.status = "failed"
        else:
            row.status = "pending"
            row.next_attempt_at = _now() + _retry_delay(attempts)
        row.last_error = error
        session.commit()


@celery_app.task(name="watchlog.email.cleanup_tokens")
def cleanup_email_tokens() -> int:
    sessionmaker = get_worker_runtime().sessionmaker
    cutoff = _now() - timedelta(days=TOKEN_RETENTION_DAYS)
    with sessionmaker() as session:
        result = session.execute(
            delete(EmailToken).where(
                or_(EmailToken.expires_at < cutoff, EmailToken.consumed_at < cutoff),
            )
        )
        session.commit()
        return int(result.rowcount or 0)


@celery_app.task(name="watchlog.email.cleanup_outbox")
def cleanup_email_outbox() -> int:
    sessionmaker = get_worker_runtime().sessionmaker
    cutoff = _now() - timedelta(days=OUTBOX_RETENTION_DAYS)
    with sessionmaker() as session:
        result = session.execute(
            delete(EmailOutbox).where(
                EmailOutbox.status.in_(("sent", "failed")),
                EmailOutbox.created_at < cutoff,
            )
        )
        session.commit()
        return int(result.rowcount or 0)
