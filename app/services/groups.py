from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.tmdb import TMDBClient
from app.core.errors import AppError
from app.models.group import Group, GroupMembership, GroupMovie, Review
from app.models.movie import Movie
from app.models.user import User
from app.schemas.groups import (
    GroupDetail,
    GroupFilm,
    GroupFilmList,
    GroupFilmScores,
    GroupList,
    GroupMember,
    GroupPreview,
    GroupStats,
    MemberScore,
    MemberScoreStats,
    MovieSummary,
)
from app.services.movies import get_or_create_movie
from app.services.scores import round_score, score_decimal
from app.services.viewer import color_for, initials_for


async def _get_group(db: AsyncSession, group_id: UUID) -> Group:
    group = await db.get(Group, group_id)
    if group is None:
        raise AppError("Group not found.", code="not_found", status_code=404)
    return group


async def _get_group_movie(db: AsyncSession, group_id: UUID, film_id: int) -> GroupMovie:
    group_movie = await db.scalar(select(GroupMovie).where(GroupMovie.id == film_id, GroupMovie.group_id == group_id))
    if group_movie is None:
        raise AppError("Film not found.", code="not_found", status_code=404)
    return group_movie


async def _members(db: AsyncSession, group_id: UUID) -> list[GroupMember]:
    rows = await db.execute(
        select(User, GroupMembership)
        .join(GroupMembership, GroupMembership.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(User.username)
    )
    return [
        GroupMember(
            id=user.id,
            username=user.username,
            initials=initials_for(user.username),
            color=color_for(user.id),
            role=membership.role,
        )
        for user, membership in rows
    ]


async def _film_count(db: AsyncSession, group_id: UUID) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(GroupMovie).where(GroupMovie.group_id == group_id)) or 0
    )


async def _member_count(db: AsyncSession, group_id: UUID) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == group_id))
        or 0
    )


async def _member_score_count(db: AsyncSession, group_id: UUID, group_movie_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(Review.id))
            .join(
                GroupMembership,
                and_(GroupMembership.user_id == Review.user_id, GroupMembership.group_id == group_id),
            )
            .where(Review.group_movie_id == group_movie_id)
        )
        or 0
    )


async def _summary(db: AsyncSession, group: Group) -> GroupDetail:
    members = await _members(db, group.id)
    return GroupDetail(
        id=group.id,
        name=group.name,
        description=group.description,
        member_count=len(members),
        film_count=await _film_count(db, group.id),
        members=members,
        created_at=group.created_at,
    )


async def list_groups(db: AsyncSession, user: User) -> GroupList:
    groups = list(
        await db.scalars(
            select(Group)
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .where(GroupMembership.user_id == user.id)
            .order_by(Group.name)
        )
    )
    summaries = []
    for group in groups:
        summaries.append(await _summary(db, group))
    return GroupList(groups=summaries)


async def create_group(db: AsyncSession, user: User, name: str, description: str | None) -> GroupDetail:
    group = Group(name=name, description=description or None)
    db.add(group)
    await db.flush()
    db.add(GroupMembership(group_id=group.id, user_id=user.id, role="admin"))
    await db.commit()
    await db.refresh(group)
    return await _summary(db, group)


async def get_group_detail(db: AsyncSession, group: Group) -> GroupDetail:
    return await _summary(db, group)


async def get_group_preview(db: AsyncSession, user: User, group_id: UUID) -> GroupPreview:
    group = await _get_group(db, group_id)
    membership = await db.scalar(
        select(GroupMembership.user_id).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        )
    )
    return GroupPreview(
        id=group.id,
        name=group.name,
        description=group.description,
        member_count=await _member_count(db, group.id),
        film_count=await _film_count(db, group.id),
        is_member=membership is not None,
    )


async def join_group(db: AsyncSession, user: User, group_id: UUID) -> GroupDetail:
    group = await _get_group(db, group_id)
    membership = await db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        )
    )
    if membership is None:
        db.add(GroupMembership(group_id=group.id, user_id=user.id, role="member"))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return await _summary(db, group)


async def leave_group(db: AsyncSession, group: Group, user: User) -> None:
    membership = await db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise AppError("You are not a member of this group.", code="not_a_member", status_code=403)
    await db.delete(membership)
    await db.commit()
    await _recompute_watched_statuses(db, group.id)


async def _recompute_watched_statuses(db: AsyncSession, group_id: UUID) -> None:
    member_count = await _member_count(db, group_id)
    if member_count == 0:
        return
    group_movies = list(await db.scalars(select(GroupMovie).where(GroupMovie.group_id == group_id)))
    for group_movie in group_movies:
        if await _member_score_count(db, group_id, group_movie.id) >= member_count:
            group_movie.status = "watched"
    await db.commit()


async def add_film(
    db: AsyncSession,
    user: User,
    group: Group,
    tmdb_id: int,
    media_type: str,
    client: TMDBClient,
) -> GroupFilm:
    movie = await get_or_create_movie(db, tmdb_id, media_type, client)
    group_movie = await db.scalar(
        select(GroupMovie).where(
            GroupMovie.group_id == group.id,
            GroupMovie.movie_id == movie.id,
        )
    )
    if group_movie is None:
        group_movie = GroupMovie(group_id=group.id, movie_id=movie.id, suggested_by_id=user.id)
        db.add(group_movie)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            group_movie = await db.scalar(
                select(GroupMovie).where(
                    GroupMovie.group_id == group.id,
                    GroupMovie.movie_id == movie.id,
                )
            )
            if group_movie is None:
                raise
        await db.refresh(group_movie)
    return await _build_film(db, group_movie, user.id)


async def _build_film(db: AsyncSession, group_movie: GroupMovie, viewer_id: int) -> GroupFilm:
    movie = await db.get(Movie, group_movie.movie_id)
    if movie is None:
        raise AppError("Movie not found.", code="not_found", status_code=404)

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
    your_score = await db.scalar(
        select(Review.score).where(
            Review.group_movie_id == group_movie.id,
            Review.user_id == viewer_id,
        )
    )
    added_by = None
    if group_movie.suggested_by_id is not None:
        added_by = await db.scalar(select(User.username).where(User.id == group_movie.suggested_by_id))

    return GroupFilm(
        id=group_movie.id,
        movie=MovieSummary.model_validate(movie),
        status=group_movie.status,
        added_at=group_movie.added_at,
        added_by=added_by,
        club_score=round_score(average),
        score_count=int(count),
        your_score=float(your_score) if your_score is not None else None,
    )


async def get_watchlist(db: AsyncSession, group: Group, viewer: User) -> GroupFilmList:
    group_movies = list(
        await db.scalars(
            select(GroupMovie)
            .where(GroupMovie.group_id == group.id)
            .order_by(GroupMovie.added_at.desc(), GroupMovie.id.desc())
        )
    )
    films = []
    for group_movie in group_movies:
        films.append(await _build_film(db, group_movie, viewer.id))
    return GroupFilmList(films=films)


async def set_score(db: AsyncSession, group: Group, user: User, film_id: int, score: float) -> GroupFilm:
    group_movie = await _get_group_movie(db, group.id, film_id)
    review = await db.scalar(
        select(Review).where(
            Review.group_movie_id == group_movie.id,
            Review.user_id == user.id,
        )
    )
    score_value = score_decimal(score)
    if review is None:
        review = Review(group_movie_id=group_movie.id, user_id=user.id, score=score_value)
        db.add(review)
    else:
        review.score = score_value

    await db.flush()
    member_count = await _member_count(db, group.id)
    if member_count and await _member_score_count(db, group.id, group_movie.id) >= member_count:
        group_movie.status = "watched"
    await db.commit()
    await db.refresh(group_movie)
    return await _build_film(db, group_movie, user.id)


async def set_film_status(db: AsyncSession, group: Group, user: User, film_id: int, status: str) -> GroupFilm:
    group_movie = await _get_group_movie(db, group.id, film_id)
    group_movie.status = status
    await db.commit()
    await db.refresh(group_movie)
    return await _build_film(db, group_movie, user.id)


async def get_film_scores(db: AsyncSession, group: Group, film_id: int) -> GroupFilmScores:
    group_movie = await _get_group_movie(db, group.id, film_id)
    rows = await db.execute(
        select(Review, User)
        .join(User, User.id == Review.user_id)
        .join(
            GroupMembership,
            and_(
                GroupMembership.user_id == Review.user_id,
                GroupMembership.group_id == group.id,
            ),
        )
        .where(Review.group_movie_id == group_movie.id)
        .order_by(User.username)
    )
    scores = [
        MemberScore(
            user_id=user.id,
            username=user.username,
            initials=initials_for(user.username),
            color=color_for(user.id),
            score=float(review.score),
        )
        for review, user in rows
    ]
    return GroupFilmScores(film_id=group_movie.id, scores=scores)


async def get_group_stats(db: AsyncSession, group: Group) -> GroupStats:
    film_count = await _film_count(db, group.id)
    watched_count = int(
        await db.scalar(
            select(func.count())
            .select_from(GroupMovie)
            .where(GroupMovie.group_id == group.id, GroupMovie.status == "watched")
        )
        or 0
    )
    member_count = await _member_count(db, group.id)
    average = await db.scalar(
        select(func.avg(Review.score))
        .join(GroupMovie, Review.group_movie_id == GroupMovie.id)
        .join(
            GroupMembership,
            and_(
                GroupMembership.user_id == Review.user_id,
                GroupMembership.group_id == group.id,
            ),
        )
        .where(GroupMovie.group_id == group.id)
    )
    rows = await db.execute(
        select(User.id, User.username, func.count(Review.id), func.avg(Review.score))
        .join(Review, Review.user_id == User.id)
        .join(GroupMovie, Review.group_movie_id == GroupMovie.id)
        .join(
            GroupMembership,
            and_(
                GroupMembership.user_id == User.id,
                GroupMembership.group_id == group.id,
            ),
        )
        .where(GroupMovie.group_id == group.id)
        .group_by(User.id, User.username)
        .order_by(User.username)
    )
    member_scores = [
        MemberScoreStats(
            user_id=user_id,
            username=username,
            score_count=int(score_count),
            average_score=round_score(average_score),
        )
        for user_id, username, score_count, average_score in rows
    ]
    return GroupStats(
        film_count=film_count,
        watched_count=watched_count,
        up_next_count=film_count - watched_count,
        member_count=member_count,
        average_score=round_score(average),
        member_scores=member_scores,
    )
