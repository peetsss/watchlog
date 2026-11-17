from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import EmailOutbox

TEMPLATE_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "templates" / "email"
_SUBJECTS: Final[dict[str, str]] = {
    "verify_email": "Confirm your watchlog email",
    "reset_password": "Reset your watchlog password",
    "password_changed": "Your watchlog password changed",
    "email_changed": "Your watchlog email changed",
}
_environment = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(("html", "xml")),
)


def subject_for(template: str) -> str:
    try:
        return _SUBJECTS[template]
    except KeyError as exc:
        raise ValueError(f"Unknown email template: {template}") from exc


def render_email(template: str, context: dict[str, object]) -> tuple[str, str, str]:
    subject = subject_for(template)
    html = _environment.get_template(f"{template}.html").render(**context)
    text = _environment.get_template(f"{template}.txt").render(**context)
    return subject, html, text


def queue_email(
    db: AsyncSession,
    *,
    template: str,
    recipient: str,
    payload: dict[str, object],
) -> EmailOutbox:
    subject_for(template)
    row = EmailOutbox(
        template=template,
        recipient=recipient.lower(),
        payload=payload,
        status="pending",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(row)
    return row
