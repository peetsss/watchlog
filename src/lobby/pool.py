from collections.abc import Iterable

from groups.models import Group, GroupMovie
from lobby import rules
from lobby.exceptions import InvalidPoolError
from movies.models import Movie


def normalize_pool(movie_ids: Iterable[int]) -> tuple[int, ...]:
    normalized: dict[int, None] = {}
    for movie_id in movie_ids:
        if isinstance(movie_id, bool) or not isinstance(movie_id, int) or movie_id <= 0:
            raise InvalidPoolError(f"Invalid movie id in pool: {movie_id!r}")
        normalized[movie_id] = None
    return tuple(normalized)


def select_random_pool(group: Group | None = None, size: int = rules.POOL_SIZE) -> list[int]:
    if size < 1:
        raise InvalidPoolError(f"Pool size must be at least 1, got {size}")
    movies = Movie.objects.filter(adult=False)
    if group is not None:
        movies = movies.exclude(id__in=GroupMovie.objects.filter(group=group).values("movie_id"))
    return list(movies.order_by("?").values_list("id", flat=True)[:size])


def resolve_pool(
    pool: Iterable[int] | None,
    group: Group | None = None,
    size: int = rules.POOL_SIZE,
) -> list[int]:
    if pool is None:
        return select_random_pool(group=group, size=size)
    normalized = normalize_pool(pool)
    if not normalized:
        return []
    existing = set(Movie.objects.filter(id__in=normalized).values_list("id", flat=True))
    missing = [movie_id for movie_id in normalized if movie_id not in existing]
    if missing:
        raise InvalidPoolError(f"Unknown movie ids in pool: {missing}")
    return list(normalized)
