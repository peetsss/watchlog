from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.schemas.home import HomeResponse
from app.services import home as home_service

router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("", response_model=HomeResponse)
async def home(user: CurrentUser, db: SessionDep) -> HomeResponse:
    return await home_service.get_home(db, user)
