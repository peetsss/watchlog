from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.core.rate_limit import rate_limit
from app.schemas.groups import GroupDetail, GroupPreview
from app.services import groups as group_service
from app.services import invites as invite_service

router = APIRouter(prefix="/api/group-invites", tags=["groups"])


@router.get(
    "/{token}",
    response_model=GroupPreview,
    dependencies=[Depends(rate_limit("group_invites.preview", 60, 60, scope="viewer"))],
)
async def preview_invite(token: str, user: CurrentUser, db: SessionDep) -> GroupPreview:
    group = await invite_service.get_invite_group(db, token)
    return await group_service.get_group_preview(db, user, group.id)


@router.post(
    "/{token}/join",
    response_model=GroupDetail,
    dependencies=[Depends(rate_limit("group_invites.join", 20, 3600, scope="viewer"))],
)
async def join_invite(token: str, user: CurrentUser, db: SessionDep) -> GroupDetail:
    group = await invite_service.join_invite(db, token, user)
    return await group_service.get_group_detail(db, group)
