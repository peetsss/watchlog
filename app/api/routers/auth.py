from fastapi import APIRouter, Request, Response, status

from app.api.deps import SessionStoreDep, SettingsDep
from app.core.db import SessionDep
from app.core.errors import AppError
from app.core.sessions import clear_auth_cookies, set_auth_cookies, set_csrf_cookie, set_session_cookie
from app.schemas.auth import CSRFResponse, LoginRequest, RegisterRequest, ViewerEnvelope
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
    user = await create_user(db, payload.username, payload.password)
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
    user = await authenticate(db, payload.username, payload.password)
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
