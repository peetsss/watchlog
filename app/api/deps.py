from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.tmdb import TMDBClient
from app.core.config import Settings
from app.core.db import SessionDep
from app.core.errors import AppError
from app.core.sessions import SessionData, SessionStore
from app.models.group import Group, GroupMembership
from app.models.guest import Guest
from app.models.user import User
from app.realtime.hub import LobbyHub
from app.services.guest import touch_guest
from app.services.identity import Viewer


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_session_data(request: Request) -> SessionData | None:
    return getattr(request.state, "session", None)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
SessionDataDep = Annotated[SessionData | None, Depends(get_session_data)]


def get_lobby_hub(request: Request) -> LobbyHub:
    return request.app.state.hub


LobbyHubDep = Annotated[LobbyHub, Depends(get_lobby_hub)]


async def get_lobby_session(
    db: SessionDep,
    hub: LobbyHubDep,
) -> AsyncSession:
    db.info["lobby_publisher"] = hub.publish
    return db


LobbySessionDep = Annotated[AsyncSession, Depends(get_lobby_session)]


async def get_tmdb_client(settings: SettingsDep) -> AsyncIterator[TMDBClient]:
    async with TMDBClient(
        api_key=settings.tmdb_api_key.get_secret_value(),
        access_token=settings.tmdb_access_token.get_secret_value(),
    ) as client:
        yield client


TMDBDep = Annotated[TMDBClient, Depends(get_tmdb_client)]


async def get_current_user(
    request: Request,
    data: SessionDataDep,
    db: SessionDep,
    store: SessionStoreDep,
) -> User:
    if data is None or data.kind != "member" or data.user_id is None:
        raise AppError("Authentication is required.", code="unauthorized", status_code=401)

    user = await db.get(User, data.user_id)
    if user is None or not user.is_active:
        session_id = getattr(request.state, "session_id", None)
        if session_id is not None:
            await store.delete(session_id)
        raise AppError("Authentication is required.", code="unauthorized", status_code=401)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_verified_user(user: CurrentUser, settings: SettingsDep) -> User:
    if settings.require_verified_email and user.email_verified_at is None:
        raise AppError(
            "Verify your email before creating or sharing a group.",
            code="email_unverified",
            status_code=403,
        )
    return user


VerifiedUser = Annotated[User, Depends(get_verified_user)]


async def _resolve_lobby_viewer(
    data: SessionData | None,
    db: AsyncSession,
    settings: Settings,
) -> Viewer | None:
    if data is None:
        return None
    if data.kind == "member" and data.user_id is not None:
        user = await db.get(User, data.user_id)
        if user is None or not user.is_active:
            return None
        return Viewer.for_user(user)
    if data.kind == "guest" and data.guest_id is not None:
        guest = await db.get(Guest, data.guest_id)
        now = datetime.now(UTC)
        if guest is None or guest.claimed_by_user_id is not None:
            return None
        if guest.expires_at is not None and guest.expires_at <= now:
            return None
        await touch_guest(db, guest, settings.guest_session_ttl_seconds)
        return Viewer.for_guest(guest)
    return None


async def get_lobby_viewer(data: SessionDataDep, db: SessionDep, settings: SettingsDep) -> Viewer:
    viewer = await _resolve_lobby_viewer(data, db, settings)
    if viewer is None:
        raise AppError("Authentication is required.", code="unauthorized", status_code=401)
    return viewer


LobbyViewer = Annotated[Viewer, Depends(get_lobby_viewer)]


async def get_optional_lobby_viewer(
    data: SessionDataDep,
    db: SessionDep,
    settings: SettingsDep,
) -> Viewer | None:
    return await _resolve_lobby_viewer(data, db, settings)


OptionalLobbyViewer = Annotated[Viewer | None, Depends(get_optional_lobby_viewer)]


@dataclass(frozen=True)
class GroupContext:
    group: Group
    user: User


async def get_group_context(
    group_id: UUID,
    user: CurrentUser,
    db: SessionDep,
) -> GroupContext:
    group = await db.get(Group, group_id)
    if group is None:
        raise AppError("Group not found.", code="not_found", status_code=404)
    membership = await db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise AppError("You are not a member of this group.", code="not_a_member", status_code=403)
    return GroupContext(group=group, user=user)


GroupContextDep = Annotated[GroupContext, Depends(get_group_context)]
