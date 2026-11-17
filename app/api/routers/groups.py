from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, status

from app.api.deps import CurrentUser, GroupContextDep, LobbySessionDep, TMDBDep, VerifiedUser
from app.core.db import SessionDep
from app.schemas.groups import (
    AddFilmRequest,
    CreateGroupRequest,
    FilmStatusRequest,
    GroupDetail,
    GroupFilm,
    GroupFilmList,
    GroupFilmScores,
    GroupList,
    GroupPreview,
    GroupStats,
    InviteLinkResponse,
    ScoreRequest,
)
from app.schemas.lobby import LobbyStateEnvelope
from app.services import groups as group_service
from app.services import lobby as lobby_service

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=GroupList)
async def list_groups(user: CurrentUser, db: SessionDep) -> GroupList:
    return await group_service.list_groups(db, user)


@router.post("", response_model=GroupDetail, status_code=status.HTTP_201_CREATED)
async def create_group(payload: CreateGroupRequest, user: VerifiedUser, db: SessionDep) -> GroupDetail:
    return await group_service.create_group(db, user, payload.name, payload.description)


@router.get("/{group_id}/preview", response_model=GroupPreview)
async def preview_group(group_id: UUID, user: CurrentUser, db: SessionDep) -> GroupPreview:
    return await group_service.get_group_preview(db, user, group_id)


@router.get("/{group_id}", response_model=GroupDetail)
async def get_group(group_id: UUID, context: GroupContextDep, db: SessionDep) -> GroupDetail:
    return await group_service.get_group_detail(db, context.group)


@router.post("/{group_id}/lobbies", response_model=LobbyStateEnvelope, status_code=status.HTTP_201_CREATED)
async def create_group_lobby(context: GroupContextDep, db: LobbySessionDep) -> LobbyStateEnvelope:
    lobby = await lobby_service.create_lobby(db, context.user, group=context.group)
    state = await lobby_service.get_state(db, lobby.id, context.user)
    return LobbyStateEnvelope(lobby=state)


@router.get("/{group_id}/watchlist", response_model=GroupFilmList)
async def get_watchlist(context: GroupContextDep, db: SessionDep) -> GroupFilmList:
    return await group_service.get_watchlist(db, context.group, context.user)


@router.post("/{group_id}/films", response_model=GroupFilm)
async def add_film(
    payload: AddFilmRequest,
    context: GroupContextDep,
    db: SessionDep,
    tmdb: TMDBDep,
) -> GroupFilm:
    return await group_service.add_film(
        db,
        context.user,
        context.group,
        payload.tmdb_id,
        payload.media_type,
        tmdb,
    )


@router.patch("/{group_id}/films/{film_id}", response_model=GroupFilm)
async def update_film_status(
    film_id: Annotated[int, Path(ge=1)],
    payload: FilmStatusRequest,
    context: GroupContextDep,
    db: SessionDep,
) -> GroupFilm:
    return await group_service.set_film_status(db, context.group, context.user, film_id, payload.status)


@router.put("/{group_id}/films/{film_id}/score", response_model=GroupFilm)
async def set_film_score(
    film_id: Annotated[int, Path(ge=1)],
    payload: ScoreRequest,
    context: GroupContextDep,
    db: SessionDep,
) -> GroupFilm:
    return await group_service.set_score(db, context.group, context.user, film_id, payload.score)


@router.get("/{group_id}/films/{film_id}/scores", response_model=GroupFilmScores)
async def get_film_scores(
    film_id: Annotated[int, Path(ge=1)],
    context: GroupContextDep,
    db: SessionDep,
) -> GroupFilmScores:
    return await group_service.get_film_scores(db, context.group, film_id)


@router.get("/{group_id}/stats", response_model=GroupStats)
async def get_group_stats(context: GroupContextDep, db: SessionDep) -> GroupStats:
    return await group_service.get_group_stats(db, context.group)


@router.get("/{group_id}/invite", response_model=InviteLinkResponse)
async def get_invite_link(
    request: Request,
    context: GroupContextDep,
    _user: VerifiedUser,
) -> InviteLinkResponse:
    base_url = str(request.base_url).rstrip("/")
    return InviteLinkResponse(invite_link=f"{base_url}/join/group/{context.group.id}")


@router.post("/{group_id}/members", response_model=GroupDetail)
async def join_group(group_id: UUID, user: CurrentUser, db: SessionDep) -> GroupDetail:
    return await group_service.join_group(db, user, group_id)


@router.delete("/{group_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(context: GroupContextDep, db: SessionDep) -> None:
    await group_service.leave_group(db, context.group, context.user)
