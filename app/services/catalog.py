import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.tmdb import SyncTMDBClient
from app.models.movie import Movie
from app.services.movies import _as_float, _as_int, _as_list, _as_str, create_movie_from_details

logger = logging.getLogger(__name__)

MediaType = Literal["movie", "series"]

DEFAULT_MAX_DISCOVER_PAGES: Final[int] = 500
INSERT_BATCH_SIZE: Final[int] = 100
SKIP_SERIES_STATUSES: Final[frozenset[str]] = frozenset({"Canceled", "Pilot"})


@dataclass(frozen=True)
class DiscoverWindowResult:
    results: list[dict[str, object]]
    complete: bool


@dataclass(frozen=True)
class CatalogueImportStats:
    discovered: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    def __add__(self, other: CatalogueImportStats) -> CatalogueImportStats:
        return CatalogueImportStats(
            discovered=self.discovered + other.discovered,
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            skipped=self.skipped + other.skipped,
            failed=self.failed + other.failed,
        )


def should_import(details: dict[str, object], media_type: MediaType) -> bool:
    if details.get("adult") is True:
        return False
    if not _as_str(details.get("overview")):
        return False
    status = _as_str(details.get("status"))
    if media_type == "movie":
        return status == "Released"
    return status not in SKIP_SERIES_STATUSES


def refresh_movie_from_discover(movie: Movie, item: dict[str, object]) -> bool:
    changed = False
    score = _as_float(item.get("vote_average"))
    if score is not None and score != movie.tmdb_score:
        movie.tmdb_score = score
        changed = True
    votes = _as_int(item.get("vote_count"))
    if votes is not None and votes != movie.vote_count:
        movie.vote_count = votes
        changed = True
    popularity = _as_float(item.get("popularity"))
    if popularity is not None and popularity != movie.popularity:
        movie.popularity = popularity
        changed = True
    return changed


def discover_window(
    client: SyncTMDBClient,
    media_type: MediaType,
    start: date,
    end: date,
    max_pages: int = DEFAULT_MAX_DISCOVER_PAGES,
) -> DiscoverWindowResult | None:
    first = client.discover(media_type, start, end, page=1)
    if first is None:
        return None
    total_pages = _as_int(first.get("total_pages")) or 0
    results: list[dict[str, object]] = []
    seen: set[int] = set()
    fetched_pages = 0
    for page in range(1, min(total_pages, max_pages) + 1):
        payload = first if page == 1 else client.discover(media_type, start, end, page=page)
        if payload is None:
            break
        fetched_pages += 1
        for item in _as_list(payload.get("results")):
            if not isinstance(item, dict):
                continue
            tmdb_id = _as_int(item.get("id"))
            if tmdb_id is None or tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            results.append(item)
    return DiscoverWindowResult(results=results, complete=fetched_pages == total_pages)


def existing_movies_by_tmdb_id(session: Session, media_type: MediaType, tmdb_ids: list[int]) -> dict[int, Movie]:
    if not tmdb_ids:
        return {}
    rows = session.scalars(select(Movie).where(Movie.media_type == media_type, Movie.tmdb_id.in_(tmdb_ids)))
    return {int(row.tmdb_id): row for row in rows if row.tmdb_id is not None}


def import_catalogue_items(
    session: Session,
    client: SyncTMDBClient,
    media_type: MediaType,
    items: list[dict[str, object]],
    refresh_existing: bool,
) -> CatalogueImportStats:
    inserted = 0
    updated = 0
    skipped = 0
    failed = 0
    tmdb_ids = [tmdb_id for item in items if (tmdb_id := _as_int(item.get("id"))) is not None]
    discovered = len(tmdb_ids)
    known = existing_movies_by_tmdb_id(session, media_type, tmdb_ids)
    for item in items:
        tmdb_id = _as_int(item.get("id"))
        if tmdb_id is None:
            continue
        movie = known.get(tmdb_id)
        if movie is not None:
            if refresh_existing and refresh_movie_from_discover(movie, item):
                updated += 1
            continue
        details = client.get_details(tmdb_id, media_type)
        if details is None:
            failed += 1
            continue
        if not should_import(details, media_type):
            skipped += 1
            continue
        session.add(create_movie_from_details(details, media_type))
        try:
            with session.begin_nested():
                session.flush()
        except IntegrityError:
            skipped += 1
        else:
            inserted += 1
            if inserted % INSERT_BATCH_SIZE == 0:
                session.commit()
    session.commit()
    return CatalogueImportStats(
        discovered=discovered,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        failed=failed,
    )


def split_window(start: date, end: date) -> tuple[tuple[date, date], tuple[date, date]]:
    days = (end - start).days
    if days < 1:
        raise ValueError(f"Window must span at least two days to split, got {start}..{end}")
    middle = start + timedelta(days=days // 2)
    return (start, middle), (middle + timedelta(days=1), end)


def sync_catalogue_range(
    session: Session,
    client: SyncTMDBClient,
    media_type: MediaType,
    start: date,
    end: date,
    max_pages: int = DEFAULT_MAX_DISCOVER_PAGES,
    refresh_existing: bool = True,
) -> CatalogueImportStats:
    if start > end:
        raise ValueError(f"Start date {start} must not be after end date {end}")
    window = discover_window(client, media_type, start, end, max_pages)
    if window is None:
        return CatalogueImportStats()
    if not window.complete and start != end:
        left, right = split_window(start, end)
        left_stats = sync_catalogue_range(session, client, media_type, *left, max_pages, refresh_existing)
        right_stats = sync_catalogue_range(session, client, media_type, *right, max_pages, refresh_existing)
        return left_stats + right_stats
    if not window.complete:
        logger.warning(
            "TMDB discover window %s..%s for %s exceeds %s pages; importing the partial result",
            start,
            end,
            media_type,
            max_pages,
        )
    return import_catalogue_items(session, client, media_type, window.results, refresh_existing)


def _month_end(month_start: date) -> date:
    return (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def iter_month_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    if start > end:
        raise ValueError(f"Start date {start} must not be after end date {end}")
    current = start
    while current <= end:
        window_end = min(end, _month_end(current.replace(day=1)))
        yield current, window_end
        if window_end == end:
            return
        current = window_end + timedelta(days=1)


def latest_catalogue_date(session: Session, media_type: MediaType) -> date | None:
    return session.scalar(
        select(func.max(Movie.release_date)).where(Movie.media_type == media_type, Movie.release_date.is_not(None))
    )
