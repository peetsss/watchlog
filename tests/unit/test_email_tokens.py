from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.email import EmailToken
from app.models.user import User
from app.services.email_tokens import consume_email_token, hash_email_token, issue_email_token


async def _user(db: AsyncSession) -> User:
    user = User(username="alice", email="alice@example.com", password_hash="unused")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_issue_email_token_stores_only_a_hash(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    raw = await issue_email_token(db_session, user, "verify_email")

    token = await db_session.scalar(select(EmailToken).where(EmailToken.user_id == user.id))
    assert token is not None
    assert token.token_hash == hash_email_token(raw)
    assert raw != token.token_hash
    assert token.consumed_at is None


async def test_consume_email_token_marks_it_used(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    raw = await issue_email_token(db_session, user, "verify_email")

    token = await consume_email_token(db_session, raw, "verify_email")

    assert token.consumed_at is not None
    with pytest.raises(AppError, match="invalid or has expired"):
        await consume_email_token(db_session, raw, "verify_email")


async def test_reissuing_a_token_invalidates_the_previous_one(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    old_raw = await issue_email_token(db_session, user, "verify_email")
    new_raw = await issue_email_token(db_session, user, "verify_email")

    with pytest.raises(AppError):
        await consume_email_token(db_session, old_raw, "verify_email")

    assert await consume_email_token(db_session, new_raw, "verify_email") is not None


async def test_expired_token_is_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    raw = await issue_email_token(db_session, user, "reset_password")
    token = await db_session.scalar(select(EmailToken).where(EmailToken.user_id == user.id))
    assert token is not None
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(AppError, match="invalid or has expired"):
        await consume_email_token(db_session, raw, "reset_password")


async def test_change_email_token_keeps_the_target_address(db_session: AsyncSession) -> None:
    user = await _user(db_session)

    raw = await issue_email_token(db_session, user, "change_email", "NEW@example.com")
    token = await consume_email_token(db_session, raw, "change_email")

    assert token.target_email == "new@example.com"
