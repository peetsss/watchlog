from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import ViewerEnvelope
from app.services.viewer import viewer_for

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=ViewerEnvelope)
async def me(user: CurrentUser) -> ViewerEnvelope:
    return ViewerEnvelope(viewer=viewer_for(user))
