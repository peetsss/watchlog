import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import LobbySessionDep, LobbyViewer, OptionalLobbyViewer, SessionStoreDep, SettingsDep
from app.core.db import SessionDep
from app.core.rate_limit import rate_limit
from app.core.sessions import set_csrf_cookie, set_session_cookie
from app.domain.lobby.exceptions import InvalidActionError, LobbyNotFoundError, NotAMemberError
from app.models.group import Group
from app.schemas.auth import CSRFResponse
from app.schemas.lobby import (
    ActiveEnvelope,
    CreateLobbyRequest,
    JoinPreviewEnvelope,
    LobbyState,
    LobbyStateEnvelope,
)
from app.services import lobby as lobby_service
from app.services import lobby_actions
from app.services.auth import ensure_session

router = APIRouter(prefix="/api/lobby", tags=["lobby"])
logger = logging.getLogger(__name__)

_ACTION_ALIASES = {
    "ready": "ready",
    "unready": "unready",
    "start": "start",
    "vote": "vote",
    "pick": "pick",
    "advance": "advance",
    "next-round": "next_round",
    "finalize": "finalize",
    "leave": "leave",
    "end": "end",
    "restart": "restart",
}


async def _json_body(request: Request) -> dict[str, object]:
    body = await request.body()
    if not body:
        return {}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvalidActionError("Request body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise InvalidActionError("Request body must be a JSON object.")
    return payload


def _state_response(state: LobbyState, status_code: int = 200, **extra: object) -> JSONResponse:
    response = JSONResponse(
        {"lobby": state.model_dump(mode="json"), **extra},
        status_code=status_code,
    )
    response.headers["ETag"] = f'"v{state.version}"'
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


def _not_modified(version: int) -> Response:
    response = Response(status_code=status.HTTP_304_NOT_MODIFIED)
    response.headers["ETag"] = f'"v{version}"'
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/csrf/", response_model=CSRFResponse, include_in_schema=False)
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


@router.get(
    "/active/",
    response_model=ActiveEnvelope,
    dependencies=[Depends(rate_limit("lobby.active", 60, 60, scope="viewer"))],
)
async def active(viewer: LobbyViewer, db: SessionDep) -> ActiveEnvelope:
    summary = await lobby_service.get_active_lobby_for_viewer(db, viewer)
    return ActiveEnvelope(active=summary)


@router.post(
    "/",
    response_model=LobbyStateEnvelope,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("lobby.create", 20, 3600, scope="viewer"))],
)
async def create(
    viewer: LobbyViewer,
    db: LobbySessionDep,
    payload: CreateLobbyRequest | None = None,
) -> Response:
    group_uuid: UUID | None = None
    if payload is not None and payload.group_uuid is not None:
        try:
            group_uuid = UUID(payload.group_uuid)
        except ValueError as exc:
            raise InvalidActionError("group_uuid must be a valid UUID.") from exc
    group = None
    if group_uuid is not None:
        group = await db.get(Group, group_uuid)
        if group is None:
            raise LobbyNotFoundError(f"Group {group_uuid} not found.")
    lobby = await lobby_service.create_lobby(db, viewer, group=group)
    state = await lobby_service.get_state(db, lobby.id, viewer)
    return _state_response(state, status_code=status.HTTP_201_CREATED)


@router.get(
    "/{lobby_uuid}/preview/",
    response_model=JoinPreviewEnvelope,
    dependencies=[Depends(rate_limit("lobby.preview", 60, 60, scope="ip"))],
)
async def preview(lobby_uuid: UUID, viewer: OptionalLobbyViewer, db: SessionDep) -> JoinPreviewEnvelope:
    preview_data = await lobby_service.get_join_preview(db, lobby_uuid, viewer)
    if not preview_data.is_participant and preview_data.type == "group":
        raise NotAMemberError("This room is private to its group.")
    return JoinPreviewEnvelope(preview=preview_data)


@router.post(
    "/{lobby_uuid}/join/",
    response_model=LobbyStateEnvelope,
    dependencies=[Depends(rate_limit("lobby.join", 20, 3600, scope="viewer"))],
)
async def join(lobby_uuid: UUID, viewer: LobbyViewer, db: LobbySessionDep) -> Response:
    await lobby_service.join_lobby(db, lobby_uuid, viewer)
    state = await lobby_service.get_state(db, lobby_uuid, viewer)
    return _state_response(state)


@router.get(
    "/{lobby_uuid}/",
    response_model=LobbyStateEnvelope,
    dependencies=[Depends(rate_limit("lobby.state", 120, 60, scope="viewer"))],
)
async def state(lobby_uuid: UUID, request: Request, viewer: LobbyViewer, db: SessionDep) -> Response:
    current = await lobby_service.get_state(db, lobby_uuid, viewer)
    etag = f'"v{current.version}"'
    if request.headers.get("if-none-match") == etag:
        return _not_modified(current.version)
    return _state_response(current)


@router.post(
    "/{lobby_uuid}/{action}/",
    response_model=LobbyStateEnvelope,
    dependencies=[Depends(rate_limit("lobby.action", 120, 60, scope="viewer"))],
)
async def action(
    lobby_uuid: UUID,
    action: str,
    request: Request,
    viewer: LobbyViewer,
    db: LobbySessionDep,
    settings: SettingsDep,
) -> Response:
    action_name = _ACTION_ALIASES.get(action)
    if action_name is None:
        raise InvalidActionError(f"Unknown lobby action: {action!r}")
    payload = await _json_body(request)
    lobby = await lobby_actions.perform_action(db, lobby_uuid, viewer, action_name, payload)
    if action_name == "leave":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if settings.env != "test" and lobby.status in {"final_round", "finished"}:
        try:
            from app.tasks.watch_providers import prefetch_finalist_watch_providers

            prefetch_finalist_watch_providers.delay(str(lobby.id))
        except Exception:
            logger.exception("Failed to enqueue finalist watch-provider prefetch")
    current = await lobby_service.get_state(db, lobby.id, viewer)
    extra = {"previous_uuid": str(lobby_uuid)} if action_name == "restart" else {}
    return _state_response(
        current,
        status_code=status.HTTP_201_CREATED if action_name == "restart" else status.HTTP_200_OK,
        **extra,
    )
