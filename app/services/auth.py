from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import AppError
from app.core.sessions import SessionData, SessionStore, new_session, ttl_for
from app.models.user import User
from app.services.moderation import is_allowed_name
from app.services.passwords import hash_password, verify_dummy_password, verify_password


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def create_user(db: AsyncSession, username: str, email: str, password: str) -> User:
    normalized_email = _normalize_email(email)
    if not is_allowed_name(username):
        raise AppError(
            "That username isn't allowed. Pick another one.",
            code="username_not_allowed",
            status_code=400,
        )
    if await db.scalar(select(User.id).where(User.username == username)) is not None:
        raise AppError("That username is already taken.", code="username_taken", status_code=409)
    if await db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
        raise AppError("That email is already in use.", code="email_taken", status_code=409)

    user = User(
        username=username,
        email=normalized_email,
        password_hash=await hash_password(password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if await db.scalar(select(User.id).where(User.username == username)) is not None:
            raise AppError("That username is already taken.", code="username_taken", status_code=409) from exc
        if await db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
            raise AppError("That email is already in use.", code="email_taken", status_code=409) from exc
        raise
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, identifier: str, password: str) -> User | None:
    user = await db.scalar(
        select(User).where(
            or_(
                User.username == identifier,
                func.lower(User.email) == identifier.lower(),
            )
        )
    )
    if user is None:
        await verify_dummy_password(password)
        return None
    if not user.is_active:
        return None
    if not await verify_password(password, user.password_hash):
        return None
    return user


async def set_password(db: AsyncSession, user: User, password: str) -> None:
    user.password_hash = await hash_password(password)
    await db.flush()


async def start_member_session(
    request: Request,
    store: SessionStore,
    settings: Settings,
    user: User,
) -> tuple[str, SessionData]:
    data = new_session("member", user_id=user.id)
    ttl = ttl_for("member", settings)
    old_session_id = getattr(request.state, "session_id", None)
    if old_session_id:
        session_id = await store.rotate(old_session_id, data, ttl)
    else:
        session_id = await store.create(data, ttl)
    request.state.session = data
    request.state.session_id = session_id
    return session_id, data


async def ensure_session(request: Request, store: SessionStore, settings: Settings) -> tuple[str, SessionData]:
    existing = getattr(request.state, "session", None)
    existing_id = getattr(request.state, "session_id", None)
    if existing is not None and existing_id is not None:
        return existing_id, existing
    data = new_session("anonymous")
    session_id = await store.create(data, ttl_for("anonymous", settings))
    request.state.session = data
    request.state.session_id = session_id
    return session_id, data
