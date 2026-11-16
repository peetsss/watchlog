from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.tmdb import BACKDROP_BASE_URL, POSTER_BASE_URL, TMDBClient
from app.core.errors import AppError
from app.models.movie import Movie
from app.schemas.movies import MovieSearchResult


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _parse_date(value: object) -> date | None:
    text = _as_str(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _join_names(items: object, key: str = "name") -> str | None:
    names: list[str] = []
    for item in _as_list(items):
        if not isinstance(item, dict):
            continue
        name = _as_str(item.get(key))
        if name is not None:
            names.append(name)
    return ", ".join(names) if names else None


def _full_url(base_url: str, value: object) -> str | None:
    path = _as_str(value)
    return f"{base_url}{path}" if path else None


def create_movie_from_details(details: dict[str, object], media_type: str) -> Movie:
    if media_type not in {"movie", "series"}:
        raise ValueError(f"Unsupported media type: {media_type}")

    tmdb_id = _as_int(details.get("id"))
    if tmdb_id is None:
        raise ValueError("TMDB details are missing a numeric id")

    credits = _as_dict(details.get("credits"))
    crew = _as_list(credits.get("crew"))
    cast = _as_list(credits.get("cast"))
    keywords_block = _as_dict(details.get("keywords"))
    keywords = _as_list(keywords_block.get("keywords")) or _as_list(keywords_block.get("results"))
    external_ids = _as_dict(details.get("external_ids"))
    imdb_id = _as_str(external_ids.get("imdb_id"))
    runtimes = _as_list(details.get("episode_run_time"))
    runtime = _as_int(details.get("runtime"))
    if runtime is None and runtimes:
        runtime = _as_int(runtimes[0])

    return Movie(
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        title=_as_str(details.get("title")) or _as_str(details.get("name")) or "",
        original_title=_as_str(details.get("original_title")) or _as_str(details.get("original_name")),
        media_type=media_type,
        description=_as_str(details.get("overview")),
        tagline=_as_str(details.get("tagline")),
        status=_as_str(details.get("status")),
        runtime=runtime,
        release_date=_parse_date(details.get("release_date") or details.get("first_air_date")),
        adult=details.get("adult") is True,
        genres=_join_names(details.get("genres")),
        keywords=_join_names(keywords),
        director=_join_names([item for item in crew if isinstance(item, dict) and item.get("job") == "Director"]),
        writers=_join_names(
            [item for item in crew if isinstance(item, dict) and item.get("job") in {"Writer", "Screenplay", "Story"}]
        ),
        actors=_join_names(cast),
        country=_join_names(details.get("production_countries")),
        original_language=_as_str(details.get("original_language")),
        spoken_languages=_join_names(details.get("spoken_languages")),
        production_companies=_join_names(details.get("production_companies")),
        poster_path=_full_url(POSTER_BASE_URL, details.get("poster_path")),
        backdrop_path=_full_url(BACKDROP_BASE_URL, details.get("backdrop_path")),
        tmdb_score=_as_float(details.get("vote_average")),
        revenue=_as_int(details.get("revenue")),
        budget=_as_int(details.get("budget")),
        imdb_url=f"https://www.imdb.com/title/{imdb_id}" if imdb_id else None,
        homepage=_as_str(details.get("homepage")),
    )


async def get_or_create_movie(
    db: AsyncSession,
    tmdb_id: int,
    media_type: str,
    client: TMDBClient,
) -> Movie:
    if media_type not in {"movie", "series"}:
        raise ValueError(f"Unsupported media type: {media_type}")

    existing = await db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if existing is not None:
        return existing

    details = await client.get_details(tmdb_id, media_type)
    if details is None:
        raise AppError("Failed to fetch movie details from TMDB.", code="tmdb_unavailable", status_code=502)

    movie = create_movie_from_details(details, media_type)
    db.add(movie)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
        if existing is not None:
            return existing
        raise
    await db.refresh(movie)
    return movie


async def attach_local_ids(db: AsyncSession, results: list[MovieSearchResult]) -> list[MovieSearchResult]:
    tmdb_ids = [result.tmdb_id for result in results]
    if not tmdb_ids:
        return results
    rows = await db.execute(select(Movie.tmdb_id, Movie.id).where(Movie.tmdb_id.in_(tmdb_ids)))
    mapping = {int(tmdb_id): int(movie_id) for tmdb_id, movie_id in rows if tmdb_id is not None}
    return [result.model_copy(update={"movie_id": mapping.get(result.tmdb_id)}) for result in results]
