from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.user import User
from app.services.auth import set_password
from app.services.email_tokens import consume_email_token, issue_email_token
from app.services.mail import queue_email
from app.services.passwords import verify_password


def _public_url(settings: Settings) -> str:
    return settings.public_url or ""


async def _queue_verification(db: AsyncSession, settings: Settings, user: User, email: str) -> None:
    token = await issue_email_token(db, user, "verify_email")
    queue_email(
        db,
        template="verify_email",
        recipient=email,
        payload={
            "username": user.username,
            "public_url": _public_url(settings),
            "token": token,
        },
    )


async def queue_verification_email(db: AsyncSession, settings: Settings, user: User) -> None:
    if user.email is None:
        raise AppError("Add an email address before requesting verification.", code="email_missing", status_code=400)
    await _queue_verification(db, settings, user, user.email)
    await db.commit()


async def resend_verification(db: AsyncSession, settings: Settings, email: str) -> None:
    user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not user.is_active or user.email_verified_at is not None or user.email is None:
        return
    await _queue_verification(db, settings, user, user.email)
    await db.commit()


async def request_password_reset(db: AsyncSession, settings: Settings, email: str) -> None:
    user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not user.is_active or user.email is None or user.email_verified_at is None:
        return
    token = await issue_email_token(db, user, "reset_password")
    queue_email(
        db,
        template="reset_password",
        recipient=user.email,
        payload={
            "username": user.username,
            "public_url": _public_url(settings),
            "token": token,
        },
    )
    await db.commit()


async def verify_email(db: AsyncSession, raw_token: str) -> User:
    token = await consume_email_token(db, raw_token, ("verify_email", "change_email"))
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AppError("This link is invalid or has expired.", code="invalid_token", status_code=400)

    now = datetime.now(UTC)
    if token.purpose == "verify_email":
        user.email_verified_at = now
        user.pending_email = None
    else:
        target_email = token.target_email
        if target_email is None:
            raise AppError("This link is invalid or has expired.", code="invalid_token", status_code=400)
        existing = await db.scalar(
            select(User.id).where(
                User.id != user.id,
                func.lower(User.email) == target_email.lower(),
            )
        )
        if existing is not None:
            raise AppError("That email is already in use.", code="email_taken", status_code=409)
        previous_email = user.email
        user.email = target_email.lower()
        user.email_verified_at = now
        user.pending_email = None
        if previous_email is not None:
            queue_email(
                db,
                template="email_changed",
                recipient=previous_email,
                payload={"username": user.username, "email": user.email},
            )

    await db.commit()
    await db.refresh(user)
    return user


async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> User:
    token = await consume_email_token(db, raw_token, "reset_password")
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AppError("This link is invalid or has expired.", code="invalid_token", status_code=400)
    await set_password(db, user, new_password)
    if user.email is not None:
        queue_email(
            db,
            template="password_changed",
            recipient=user.email,
            payload={"username": user.username},
        )
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not await verify_password(current_password, user.password_hash):
        raise AppError("That password is not correct.", code="invalid_credentials", status_code=401)
    await set_password(db, user, new_password)
    if user.email is not None:
        queue_email(
            db,
            template="password_changed",
            recipient=user.email,
            payload={"username": user.username},
        )
    await db.commit()


async def change_email(
    db: AsyncSession,
    settings: Settings,
    user: User,
    new_email: str,
    password: str,
) -> None:
    if not await verify_password(password, user.password_hash):
        raise AppError("That password is not correct.", code="invalid_credentials", status_code=401)
    normalized = new_email.strip().lower()
    if normalized == user.email:
        raise AppError("That is already your email.", code="email_unchanged", status_code=400)
    existing = await db.scalar(
        select(User.id).where(
            User.id != user.id,
            func.lower(User.email) == normalized,
        )
    )
    if existing is not None:
        raise AppError("That email is already in use.", code="email_taken", status_code=409)

    token = await issue_email_token(db, user, "change_email", normalized)
    user.pending_email = normalized
    queue_email(
        db,
        template="verify_email",
        recipient=normalized,
        payload={
            "username": user.username,
            "public_url": _public_url(settings),
            "token": token,
        },
    )
    await db.commit()
