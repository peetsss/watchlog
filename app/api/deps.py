from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select

from app.clients.tmdb import TMDBClient
from app.core.config import Settings
from app.core.db import SessionDep
from app.core.errors import AppError
from app.core.sessions import SessionData, SessionStore
from app.models.group import Group, GroupMembership
from app.models.user import User


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_session_data(request: Request) -> SessionData | None:
    return getattr(request.state, "session", None)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
SessionDataDep = Annotated[SessionData | None, Depends(get_session_data)]


async def get_tmdb_client(settings: SettingsDep) -> AsyncIterator[TMDBClient]:
    async with TMDBClient(api_key=settings.tmdb_api_key.get_secret_value()) as client:
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
