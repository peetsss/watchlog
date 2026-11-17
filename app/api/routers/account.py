from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.core.rate_limit import rate_limit
from app.models.group import Group, GroupMembership, GroupMovie, Review
from app.models.movie import Movie
from app.schemas.auth import AccountEnvelope

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("", response_model=AccountEnvelope)
async def get_account(user: CurrentUser) -> AccountEnvelope:
    return AccountEnvelope(
        username=user.username,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        pending_email=user.pending_email,
        region=user.region,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@router.get(
    "/export",
    dependencies=[Depends(rate_limit("account.export", 5, 3600, scope="viewer"))],
)
async def export_account(user: CurrentUser, db: SessionDep) -> JSONResponse:
    memberships = list(
        await db.execute(
            select(Group, GroupMembership)
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .where(GroupMembership.user_id == user.id)
            .order_by(Group.name)
        )
    )
    scores = list(
        await db.execute(
            select(Review, GroupMovie, Group, Movie)
            .join(GroupMovie, GroupMovie.id == Review.group_movie_id)
            .join(Group, Group.id == GroupMovie.group_id)
            .join(Movie, Movie.id == GroupMovie.movie_id)
            .where(Review.user_id == user.id)
            .order_by(Review.created_at)
        )
    )
    payload: dict[str, object] = {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "username": user.username,
            "email": user.email,
            "email_verified": user.email_verified_at is not None,
            "region": user.region,
            "created_at": _iso(user.created_at),
        },
        "groups": [
            {
                "id": str(group.id),
                "name": group.name,
                "role": membership.role,
                "joined_at": _iso(membership.joined_at),
            }
            for group, membership in memberships
        ],
        "film_scores": [
            {
                "film_id": group_movie.id,
                "group_id": str(group.id),
                "group_name": group.name,
                "movie_title": movie.title,
                "score": float(review.score),
                "comment": review.comment,
                "contains_spoilers": review.contains_spoilers,
                "created_at": _iso(review.created_at),
                "updated_at": _iso(review.updated_at),
            }
            for review, group_movie, group, movie in scores
        ],
    }
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": 'attachment; filename="watchlog-export.json"',
            "Cache-Control": "no-store",
        },
    )
