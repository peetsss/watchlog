from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, SessionStoreDep, SettingsDep
from app.core.db import SessionDep
from app.core.errors import AppError
from app.core.sessions import clear_auth_cookies, set_auth_cookies, set_csrf_cookie, set_session_cookie
from app.schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    CSRFResponse,
    EmailRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    ViewerEnvelope,
)
from app.services import account as account_service
from app.services.auth import authenticate, create_user, ensure_session, start_member_session
from app.services.viewer import viewer_for

router = APIRouter(prefix="/api/auth", tags=["auth"])


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


@router.post("/register", response_model=ViewerEnvelope, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> ViewerEnvelope:
    user = await create_user(db, payload.username, str(payload.email), payload.password)
    await account_service.queue_verification_email(db, settings, user)
    session_id, data = await start_member_session(request, store, settings, user)
    set_auth_cookies(response, session_id, data, settings)
    return ViewerEnvelope(viewer=viewer_for(user))


@router.post("/login", response_model=ViewerEnvelope)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    store: SessionStoreDep,
) -> ViewerEnvelope:
    user = await authenticate(db, payload.identifier, payload.password)
    if user is None:
        raise AppError("Invalid username or password.", code="invalid_credentials", status_code=401)
    session_id, data = await start_member_session(request, store, settings, user)
    set_auth_cookies(response, session_id, data, settings)
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


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(payload: VerifyEmailRequest, db: SessionDep) -> Response:
    await account_service.verify_email(db, payload.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    payload: EmailRequest,
    db: SessionDep,
    settings: SettingsDep,
) -> Response:
    await account_service.resend_verification(db, settings, str(payload.email))
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: EmailRequest,
    db: SessionDep,
    settings: SettingsDep,
) -> Response:
    await account_service.request_password_reset(db, settings, str(payload.email))
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    payload: ResetPasswordRequest,
    db: SessionDep,
    store: SessionStoreDep,
) -> Response:
    user = await account_service.reset_password(db, payload.token, payload.new_password)
    await store.revoke_user_sessions(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: SessionDep,
    store: SessionStoreDep,
) -> Response:
    await account_service.change_password(db, user, payload.current_password, payload.new_password)
    await store.revoke_user_sessions(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-email", status_code=status.HTTP_202_ACCEPTED)
async def change_email(
    payload: ChangeEmailRequest,
    user: CurrentUser,
    db: SessionDep,
    settings: SettingsDep,
) -> Response:
    await account_service.change_email(db, settings, user, str(payload.new_email), payload.password)
    return Response(status_code=status.HTTP_202_ACCEPTED)
