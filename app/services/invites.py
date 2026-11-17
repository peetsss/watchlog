import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.group import Group, GroupMembership
from app.models.invite import GroupInvite
from app.models.user import User

INVITE_TTL_SECONDS: Final[int] = 7 * 24 * 60 * 60
INVITE_TOKEN_BYTES: Final[int] = 32


def hash_invite_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_invite(db: AsyncSession, group: Group, user: User) -> str:
    now = datetime.now(UTC)
    await db.execute(
        update(GroupInvite)
        .where(
            GroupInvite.group_id == group.id,
            GroupInvite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    raw_token = secrets.token_urlsafe(INVITE_TOKEN_BYTES)
    db.add(
        GroupInvite(
            group_id=group.id,
            created_by_id=user.id,
            token_hash=hash_invite_token(raw_token),
            expires_at=now + timedelta(seconds=INVITE_TTL_SECONDS),
        )
    )
    await db.commit()
    return raw_token


async def get_invite(db: AsyncSession, raw_token: str) -> GroupInvite:
    invitation = await db.scalar(
        select(GroupInvite).where(
            GroupInvite.token_hash == hash_invite_token(raw_token),
            GroupInvite.revoked_at.is_(None),
            GroupInvite.expires_at > datetime.now(UTC),
        )
    )
    if invitation is None:
        raise AppError("This invite is invalid or has expired.", code="invalid_invite", status_code=404)
    return invitation


async def get_invite_group(db: AsyncSession, raw_token: str) -> Group:
    invitation = await get_invite(db, raw_token)
    group = await db.get(Group, invitation.group_id)
    if group is None:
        raise AppError("This invite is invalid or has expired.", code="invalid_invite", status_code=404)
    return group


async def join_invite(db: AsyncSession, raw_token: str, user: User) -> Group:
    group = await get_invite_group(db, raw_token)
    membership = await db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        )
    )
    if membership is None:
        db.add(GroupMembership(group_id=group.id, user_id=user.id, role="member"))
        await db.commit()
    return group


async def revoke_invites(db: AsyncSession, group: Group) -> int:
    result = await db.execute(
        update(GroupInvite)
        .where(
            GroupInvite.group_id == group.id,
            GroupInvite.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()
    return int(result.rowcount or 0)
