import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDataDep, SessionStoreDep, SettingsDep
from app.core.db import SessionDep
from app.core.errors import AppError
from app.core.rate_limit import rate_limit
from app.core.sessions import (
    clear_auth_cookies,
    new_session,
    set_auth_cookies,
    set_csrf_cookie,
    set_session_cookie,
    ttl_for,
)
from app.models.group import Review
from app.models.guest import Guest
from app.models.user import User
from app.schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    CSRFResponse,
    EmailRequest,
    GuestCreateRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionEnvelope,
    SessionViewer,
    VerifyEmailRequest,
    ViewerEnvelope,
    ViewerStats,
)
from app.services import account as account_service
from app.services.auth import authenticate, create_user, ensure_session, start_member_session
from app.services.guest import claim_guest, create_guest
from app.services.scores import round_score
from app.services.viewer import color_for, initials_for, viewer_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _guest_id_from_request(request: Request) -> UUID | None:
    session = getattr(request.state, "session", None)
    if session is None or session.kind != "guest":
        return None
    return session.guest_id


async def _member_session(db: AsyncSession, user: User) -> SessionEnvelope:
    count, average = (
        await db.execute(select(func.count(Review.id), func.avg(Review.score)).where(Review.user_id == user.id))
    ).one()
    return SessionEnvelope(
        mode="member",
        viewer=SessionViewer(
            mode="member",
            id=str(user.id),
            name=user.username,
            initials=initials_for(user.username),
            color=color_for(user.id),
            is_guest=False,
            email_verified=user.email_verified_at is not None,
        ),
        stats=ViewerStats(
            titles_watched=int(count or 0),
            average_score=round_score(average),
        ),
        email=user.email,
    )


def _guest_session(guest: Guest) -> SessionEnvelope:
    return SessionEnvelope(
        mode="guest",
        viewer=SessionViewer(
            mode="guest",
            id=str(guest.id),
            name=guest.display_name,
            initials=initials_for(guest.display_name),
            color=color_for(str(guest.id)),
            is_guest=True,
            email_verified=False,
        ),
        stats=None,
        email=None,
    )


@router.get("/csrf", response_model=CSRFResponse)
async def csrf(
    request: Request,
    response: Response,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> CSRFResponse:
    session_id, data = await ensure_session(request, store, settings)
    set_session_cookie(response, session_id, data, settings)
    set_csrf_cookie(response, data, settings)
    return CSRFResponse(csrf_token=data.csrf)


@router.get("/session", response_model=SessionEnvelope)
async def session(data: SessionDataDep, db: SessionDep) -> SessionEnvelope:
    if data is not None and data.kind == "member" and data.user_id is not None:
        user = await db.get(User, data.user_id)
        if user is not None and user.is_active:
            return await _member_session(db, user)
    if data is not None and data.kind == "guest" and data.guest_id is not None:
        guest = await db.get(Guest, data.guest_id)
        if (
            guest is not None
            and guest.claimed_by_user_id is None
            and (guest.expires_at is None or guest.expires_at > datetime.now(UTC))
        ):
            return _guest_session(guest)
    return SessionEnvelope(mode="anonymous", viewer=None, stats=None, email=None)


@router.post(
    "/guest",
    response_model=SessionEnvelope,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth.guest", 10, 3600, scope="ip"))],
)
async def guest(
    payload: GuestCreateRequest,
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> SessionEnvelope:
    current = getattr(request.state, "session", None)
    if current is not None and current.kind == "member":
        raise AppError("You are already signed in.", code="already_member", status_code=409)
    if current is not None and current.kind == "guest" and current.guest_id is not None:
        existing = await db.get(Guest, current.guest_id)
        if (
            existing is not None
            and existing.claimed_by_user_id is None
            and (existing.expires_at is None or existing.expires_at > datetime.now(UTC))
        ):
            return _guest_session(existing)

    created = await create_guest(db, payload.display_name, settings.guest_session_ttl_seconds)
    data = new_session("guest", guest_id=created.id)
    ttl = ttl_for("guest", settings)
    old_session_id = getattr(request.state, "session_id", None)
    if old_session_id is not None:
        session_id = await store.rotate(old_session_id, data, ttl)
    else:
        session_id = await store.create(data, ttl)
    request.state.session = data
    request.state.session_id = session_id
    set_auth_cookies(response, session_id, data, settings)
    return _guest_session(created)


@router.post(
    "/register",
    response_model=ViewerEnvelope,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth.register", 5, 3600, scope="ip"))],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> ViewerEnvelope:
    guest_id = _guest_id_from_request(request)
    user = await create_user(db, payload.username, str(payload.email), payload.password)
    await account_service.queue_verification_email(db, settings, user)
    session_id, data = await start_member_session(request, store, settings, user)
    set_auth_cookies(response, session_id, data, settings)
    if guest_id is not None:
        try:
            await claim_guest(db, guest_id, user)
        except Exception:
            logger.exception("Failed to claim guest %s for user %s", guest_id, user.id)
    return ViewerEnvelope(viewer=viewer_for(user))


@router.post(
    "/login",
    response_model=ViewerEnvelope,
    dependencies=[Depends(rate_limit("auth.login", 10, 900, scope="ip"))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> ViewerEnvelope:
    guest_id = _guest_id_from_request(request)
    user = await authenticate(db, payload.identifier, payload.password)
    if user is None:
        raise AppError("Invalid username or password.", code="invalid_credentials", status_code=401)
    session_id, data = await start_member_session(request, store, settings, user)
    set_auth_cookies(response, session_id, data, settings)
    if guest_id is not None:
        try:
            await claim_guest(db, guest_id, user)
        except Exception:
            logger.exception("Failed to claim guest %s for user %s", guest_id, user.id)
    return ViewerEnvelope(viewer=viewer_for(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> None:
    session_id = getattr(request.state, "session_id", None)
    if session_id is not None:
        await store.delete(session_id)
    clear_auth_cookies(response, settings)


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("auth.verify_email", 20, 3600, scope="ip"))],
)
async def verify_email(payload: VerifyEmailRequest, db: SessionDep) -> Response:
    await account_service.verify_email(db, payload.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("auth.resend", 3, 3600, scope="ip"))],
)
async def resend_verification(
    payload: EmailRequest,
    db: SessionDep,
    settings: SettingsDep,
) -> Response:
    await account_service.resend_verification(db, settings, str(payload.email))
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("auth.forgot", 3, 3600, scope="ip"))],
)
async def forgot_password(
    payload: EmailRequest,
    db: SessionDep,
    settings: SettingsDep,
) -> Response:
    await account_service.request_password_reset(db, settings, str(payload.email))
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("auth.reset", 10, 3600, scope="ip"))],
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: SessionDep,
    store: SessionStoreDep,
) -> Response:
    user = await account_service.reset_password(db, payload.token, payload.new_password)
    await store.revoke_user_sessions(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("auth.change_password", 5, 3600, scope="viewer"))],
)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: SessionDep,
    store: SessionStoreDep,
) -> Response:
    await account_service.change_password(db, user, payload.current_password, payload.new_password)
    await store.revoke_user_sessions(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/change-email",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("auth.change_email", 5, 3600, scope="viewer"))],
)
async def change_email(
    payload: ChangeEmailRequest,
    user: CurrentUser,
    db: SessionDep,
    settings: SettingsDep,
) -> Response:
    await account_service.change_email(db, settings, user, str(payload.new_email), payload.password)
    return Response(status_code=status.HTTP_202_ACCEPTED)
