from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group, GroupMembership, GroupMovie, Review
from app.models.movie import Movie
from app.models.user import User
from app.schemas.groups import MovieSummary
from app.schemas.home import HomeCrews, HomeFeaturedGroup, HomeLogEntry, HomeResponse
from app.services import groups as group_service
from app.services import lobby as lobby_service
from app.services.identity import Viewer
from app.services.scores import round_score
from app.services.viewer import viewer_for


async def _log_entries(
    db: AsyncSession,
    group_ids: list[UUID],
    *,
    group_id: UUID | None = None,
    limit: int = 8,
) -> list[HomeLogEntry]:
    if not group_ids:
        return []

    last_review = func.max(Review.updated_at)
    statement = (
        select(GroupMovie, Group.name, Movie, last_review.label("last_review"))
        .join(Group, Group.id == GroupMovie.group_id)
        .join(Movie, Movie.id == GroupMovie.movie_id)
        .outerjoin(Review, Review.group_movie_id == GroupMovie.id)
        .where(GroupMovie.status == "watched")
        .where(GroupMovie.group_id.in_(group_ids))
        .group_by(GroupMovie.id, Group.name, Movie.id)
        .order_by(func.coalesce(last_review, GroupMovie.added_at).desc(), GroupMovie.id.desc())
        .limit(limit)
    )
    if group_id is not None:
        statement = statement.where(GroupMovie.group_id == group_id)

    rows = (await db.execute(statement)).all()
    entries: list[HomeLogEntry] = []
    for group_movie, group_name, movie, last_review_at in rows:
        stats = await db.execute(
            select(func.avg(Review.score), func.count(Review.id))
            .join(
                GroupMembership,
                and_(
                    GroupMembership.user_id == Review.user_id,
                    GroupMembership.group_id == group_movie.group_id,
                ),
            )
            .where(Review.group_movie_id == group_movie.id)
        )
        average, count = stats.one()
        entries.append(
            HomeLogEntry(
                film_id=group_movie.id,
                group_id=group_movie.group_id,
                group_name=group_name,
                movie=MovieSummary.model_validate(movie),
                watched_at=last_review_at or group_movie.added_at,
                club_score=round_score(average),
                score_count=int(count),
            )
        )
    return entries


async def get_home(db: AsyncSession, user: User) -> HomeResponse:
    summaries = (await group_service.list_groups(db, user)).groups
    group_ids = [summary.id for summary in summaries]

    watched_count = 0
    if group_ids:
        watched_count = int(
            await db.scalar(
                select(func.count())
                .select_from(GroupMovie)
                .where(
                    GroupMovie.group_id.in_(group_ids),
                    GroupMovie.status == "watched",
                )
            )
            or 0
        )

    featured: HomeFeaturedGroup | None = None
    if summaries:
        summary = summaries[0]
        group = await db.get(Group, summary.id)
        up_next: list[MovieSummary] = []
        if group is not None:
            watchlist = await group_service.get_watchlist(db, group, user)
            up_next = [film.movie for film in watchlist.films if film.status == "up_next"]
        last_watched = await _log_entries(db, group_ids, group_id=summary.id, limit=1)
        featured = HomeFeaturedGroup(
            **summary.model_dump(),
            up_next_count=len(up_next),
            up_next=up_next[:4],
            last_watched=last_watched[0] if last_watched else None,
        )

    log = await _log_entries(db, group_ids, limit=8)
    active = await lobby_service.get_active_lobby_for_viewer(db, Viewer.for_user(user))

    return HomeResponse(
        viewer=viewer_for(user),
        active_lobby=active,
        crews=HomeCrews(
            count=len(summaries),
            film_count=sum(summary.film_count for summary in summaries),
            watched_count=watched_count,
        ),
        featured_group=featured,
        log=log,
    )
