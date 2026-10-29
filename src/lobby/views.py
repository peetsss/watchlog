import json
from collections.abc import Callable
from functools import wraps
from uuid import UUID

from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from groups.models import Group
from lobby import actions, selectors, services
from lobby.dto import LobbyState
from lobby.errors import error_details
from lobby.exceptions import InvalidActionError, LobbyError
from lobby.models import Lobby
from lobby.serializers import error_to_dict, preview_to_dict, state_to_dict, summary_to_dict

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


def _api_login_required(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(view)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if not request.user.is_authenticated:
            return _error_response("unauthorized", "Authentication is required.", 401)
        return view(request, *args, **kwargs)

    return wrapper


def _error_response(code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse(error_to_dict(code, message), status=status)


def _domain_error_response(exc: LobbyError) -> JsonResponse:
    status, code = error_details(exc)
    return _error_response(code, str(exc), status)


def _json_body(request: HttpRequest) -> dict[str, object]:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise InvalidActionError("Request body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise InvalidActionError("Request body must be a JSON object.")
    return payload


def _state_response(state: LobbyState, status: int = 200, **extra: object) -> JsonResponse:
    payload: dict[str, object] = {"lobby": state_to_dict(state)}
    payload.update(extra)
    response = JsonResponse(payload, status=status)
    response["ETag"] = f'"v{state.version}"'
    response["Cache-Control"] = "private, no-cache"
    response["Vary"] = "Cookie"
    return response


def _group_uuid(payload: dict[str, object]) -> UUID | None:
    raw = payload.get("group_uuid")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidActionError("group_uuid must be a UUID string.")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise InvalidActionError("group_uuid must be a valid UUID.") from exc


@require_GET
@ensure_csrf_cookie
@_api_login_required
def csrf_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"csrfToken": get_token(request)})


@_api_login_required
@require_GET
def active_view(request: HttpRequest) -> JsonResponse:
    summary = selectors.get_active_lobby_for_user(request.user)
    return JsonResponse({"active": summary_to_dict(summary) if summary is not None else None})


@_api_login_required
@require_POST
def create_view(request: HttpRequest) -> HttpResponse:
    try:
        payload = _json_body(request)
        group_uuid = _group_uuid(payload)
        group = None
        if group_uuid is not None:
            group = Group.objects.filter(uuid=group_uuid).first()
            if group is None:
                return _error_response("not_found", f"Group {group_uuid} not found.", 404)
        lobby = services.create_lobby(request.user, group=group)
        return _state_response(selectors.get_state(lobby.uuid, request.user), status=201)
    except LobbyError as exc:
        return _domain_error_response(exc)


@_api_login_required
@require_GET
def state_view(request: HttpRequest, lobby_uuid: UUID) -> HttpResponse:
    try:
        state = selectors.get_state(lobby_uuid, request.user)
    except LobbyError as exc:
        return _domain_error_response(exc)
    etag = f'"v{state.version}"'
    if request.headers.get("If-None-Match") == etag:
        response = HttpResponseNotModified()
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        response["Vary"] = "Cookie"
        return response
    return _state_response(state)


@_api_login_required
@require_GET
def preview_view(request: HttpRequest, lobby_uuid: UUID) -> HttpResponse:
    try:
        preview = selectors.get_join_preview(lobby_uuid, request.user)
    except LobbyError as exc:
        return _domain_error_response(exc)
    if not preview.is_member and preview.type == Lobby.Type.GROUP:
        return _error_response("not_a_member", "This room is private to its group.", 403)
    return JsonResponse({"preview": preview_to_dict(preview)})


@_api_login_required
@require_POST
def join_view(request: HttpRequest, lobby_uuid: UUID) -> HttpResponse:
    try:
        services.join_lobby(lobby_uuid, request.user)
        return _state_response(selectors.get_state(lobby_uuid, request.user))
    except LobbyError as exc:
        return _domain_error_response(exc)


@_api_login_required
@require_POST
def action_view(request: HttpRequest, lobby_uuid: UUID, action: str) -> HttpResponse:
    action_name = _ACTION_ALIASES.get(action)
    if action_name is None:
        return _error_response("invalid_action", f"Unknown lobby action: {action!r}", 400)
    try:
        payload = _json_body(request)
        lobby = actions.perform_action(lobby_uuid, request.user, action_name, payload)
        if action_name == "leave":
            return HttpResponse(status=204)
        state = selectors.get_state(lobby.uuid, request.user)
        status = 201 if action_name == "restart" else 200
        extra = {"previous_uuid": str(lobby_uuid)} if action_name == "restart" else {}
        return _state_response(state, status=status, **extra)
    except LobbyError as exc:
        return _domain_error_response(exc)
