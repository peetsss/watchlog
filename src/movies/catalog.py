"""Reusable TMDB -> Movie catalog resolution.

Factored out of the group add-movie view so lobby manual nominations can
resolve titles without implicitly touching `GroupMovie`. No group or
personal side effects here.
"""

from __future__ import annotations

from datetime import date, datetime

from movies.utils.tmdb import BACKDROP_BASE_URL, POSTER_BASE_URL, TMDBClient

from .models import Movie


def parse_date(value: str | None) -> date | None:
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def join_names(items: list[dict], key: str = "name") -> str | None:
    names = [item[key] for item in items if item.get(key)]
    return ", ".join(names) if names else None


def full_url(base_url: str, path: str | None) -> str | None:
    return base_url + path if path else None


def create_movie_from_details(details: dict, media_type: str) -> Movie:
    """Create a Movie row from TMDB details payload (no group writes)."""
    credits = details.get("credits") or {}
    crew = credits.get("crew") or []
    cast = credits.get("cast") or []
    keywords = (details.get("keywords") or {}).get("keywords") or []
    external_ids = details.get("external_ids") or {}
    runtimes = details.get("episode_run_time") or []
    imdb_id = external_ids.get("imdb_id") or None

    return Movie.objects.create(
        tmdb_id=details["id"],
        imdb_id=imdb_id,
        title=details.get("title") or details.get("name") or "",
        original_title=details.get("original_title") or details.get("original_name") or None,
        media_type=media_type,
        description=details.get("overview") or None,
        status=details.get("status") or None,
        runtime=details.get("runtime") or (runtimes[0] if runtimes else None),
        release_date=parse_date(details.get("release_date") or details.get("first_air_date")),
        adult=details.get("adult", False),
        genres=join_names(details.get("genres") or []),
        keywords=join_names(keywords),
        director=join_names([c for c in crew if c.get("job") == "Director"]),
        writers=join_names([c for c in crew if c.get("job") in {"Writer", "Screenplay", "Story"}]),
        actors=join_names(cast),
        country=join_names(details.get("production_countries") or []),
        poster_path=full_url(POSTER_BASE_URL, details.get("poster_path")),
        backdrop_path=full_url(BACKDROP_BASE_URL, details.get("backdrop_path")),
        tmdb_score=details.get("vote_average"),
        revenue=details.get("revenue") or None,
        budget=details.get("budget") or None,
        imdb_url=f"https://www.imdb.com/title/{imdb_id}" if imdb_id else None,
    )


def resolve_movie(
    tmdb_id: int | str,
    media_type: str,
    *,
    client: TMDBClient | None = None,
) -> Movie | None:
    """Return the catalog Movie, fetching from TMDB on miss.

    Returns None when TMDB lookup fails. Never writes `GroupMovie`.
    Idempotent: repeated calls return the same row.
    """
    if media_type not in Movie.MediaType.values:
        raise ValueError(f"invalid media type: {media_type!r}")
    existing = Movie.objects.filter(tmdb_id=tmdb_id).first()
    if existing is not None:
        return existing
    own_client = client if client is not None else TMDBClient()
    try:
        details = own_client.get_details(tmdb_id, media_type)
    finally:
        if client is None:
            own_client.close()
    if not details:
        return None
    return create_movie_from_details(details, media_type)
