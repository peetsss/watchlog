from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.lobby import rules
from app.domain.lobby.exceptions import InvalidPoolError
from app.models.group import Group, GroupMovie
from app.models.movie import Movie


def normalize_pool(movie_ids: Iterable[int]) -> tuple[int, ...]:
    normalized: dict[int, None] = {}
    for movie_id in movie_ids:
        if isinstance(movie_id, bool) or not isinstance(movie_id, int) or movie_id <= 0:
            raise InvalidPoolError(f"Invalid movie id in pool: {movie_id!r}")
        normalized[movie_id] = None
    return tuple(normalized)


async def select_random_pool(db: AsyncSession, group: Group | None = None, size: int = rules.POOL_SIZE) -> list[int]:
    if size < 1:
        raise InvalidPoolError(f"Pool size must be at least 1, got {size}")
    statement = select(Movie.id).where(Movie.adult.is_(False))
    if group is not None:
        statement = statement.where(Movie.id.not_in(select(GroupMovie.movie_id).where(GroupMovie.group_id == group.id)))
    statement = statement.order_by(func.random()).limit(size)
    return list(await db.scalars(statement))


async def resolve_pool(
    db: AsyncSession,
    pool: Iterable[int] | None,
    group: Group | None = None,
    size: int = rules.POOL_SIZE,
) -> list[int]:
    if pool is None:
        return await select_random_pool(db, group=group, size=size)

    normalized = normalize_pool(pool)
    if not normalized:
        return []
    existing = set(await db.scalars(select(Movie.id).where(Movie.id.in_(normalized))))
    missing = [movie_id for movie_id in normalized if movie_id not in existing]
    if missing:
        raise InvalidPoolError(f"Unknown movie ids in pool: {missing}")
    return list(normalized)
