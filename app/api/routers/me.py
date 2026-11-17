from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.models.group import Review
from app.schemas.auth import MeEnvelope, ViewerStats
from app.services.scores import round_score
from app.services.viewer import viewer_for

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=MeEnvelope)
async def me(user: CurrentUser, db: SessionDep) -> MeEnvelope:
    count, average = (
        await db.execute(select(func.count(Review.id), func.avg(Review.score)).where(Review.user_id == user.id))
    ).one()
    return MeEnvelope(
        viewer=viewer_for(user),
        stats=ViewerStats(
            titles_watched=int(count or 0),
            average_score=round_score(average),
        ),
        email=user.email,
    )
