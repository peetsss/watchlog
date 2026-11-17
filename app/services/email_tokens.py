import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.email import EmailToken
from app.models.user import User

EmailPurpose = Literal["verify_email", "reset_password", "change_email"]

TOKEN_BYTES: Final[int] = 32
TOKEN_TTL_SECONDS: Final[dict[str, int]] = {
    "verify_email": 24 * 60 * 60,
    "reset_password": 60 * 60,
    "change_email": 24 * 60 * 60,
}


def hash_email_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def issue_email_token(
    db: AsyncSession,
    user: User,
    purpose: EmailPurpose,
    target_email: str | None = None,
) -> str:
    await db.execute(
        delete(EmailToken).where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.consumed_at.is_(None),
        )
    )
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    token = EmailToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_email_token(raw_token),
        target_email=target_email.lower() if target_email is not None else None,
        expires_at=datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS[purpose]),
    )
    db.add(token)
    await db.flush()
    return raw_token


async def consume_email_token(db: AsyncSession, raw_token: str, purpose: EmailPurpose) -> EmailToken:
    token = await db.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == hash_email_token(raw_token),
            EmailToken.purpose == purpose,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if token is None or token.consumed_at is not None or token.expires_at <= now:
        raise AppError("This link is invalid or has expired.", code="invalid_token", status_code=400)
    token.consumed_at = now
    await db.flush()
    return token
