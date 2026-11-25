import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.celery_app import celery_app
from app.clients.tmdb import SyncTMDBWatchProviderClient
from app.core.config import get_settings
from app.models.group import GroupMovie
from app.models.lobby import Lobby
from app.models.movie import Movie
from app.models.watch import MovieWatchRegion
from app.services.watch_providers import parse_watch_providers, upsert_watch_region_sync
from app.workers.runtime import get_worker_runtime

logger = logging.getLogger(__name__)


def _is_fresh(fetched_at: datetime | None, ttl_seconds: int) -> bool:
    return fetched_at is not None and fetched_at >= datetime.now(UTC) - timedelta(seconds=ttl_seconds)


@celery_app.task(name="watchlog.watch.refresh_movie")
def refresh_movie_watch_providers(movie_id: int, region: str, force: bool = False) -> bool:
    settings = get_settings()
    sessionmaker = get_worker_runtime().sessionmaker
    with sessionmaker() as session:
        movie = session.get(Movie, movie_id)
        if movie is None or movie.tmdb_id is None:
            return False
        row = session.get(MovieWatchRegion, (movie_id, region))
        if not force and row is not None and _is_fresh(row.fetched_at, settings.watch_provider_ttl_seconds):
            return False

        try:
            with SyncTMDBWatchProviderClient(
                api_key=settings.tmdb_api_key.get_secret_value(),
                access_token=settings.tmdb_access_token.get_secret_value(),
                language=settings.tmdb_language,
                requests_per_second=settings.tmdb_rate_limit_per_second,
            ) as client:
                payload = client.get_watch_providers(movie.tmdb_id, movie.media_type)
        except Exception:
            logger.warning("TMDB watch-provider fetch failed for movie %s", movie_id)
            payload = None

        parsed = parse_watch_providers(payload, region) if payload is not None else None
        if parsed is None:
            if row is not None:
                row.last_attempt_at = datetime.now(UTC)
                row.last_error = "TMDB unavailable"
                session.commit()
            return False

        upsert_watch_region_sync(session, movie_id, region, parsed)
        session.commit()
        return True


@celery_app.task(name="watchlog.watch.refresh_stale")
def refresh_stale_watch_providers() -> int:
    settings = get_settings()
    sessionmaker = get_worker_runtime().sessionmaker
    region = settings.default_region
    with sessionmaker() as session:
        movie_ids = list(session.scalars(select(GroupMovie.movie_id).distinct()))
    queued = 0
    for movie_id in movie_ids[: settings.provider_refresh_limit]:
        refresh_movie_watch_providers.delay(movie_id, region)
        queued += 1
    return queued


@celery_app.task(name="watchlog.watch.prefetch_finalists")
def prefetch_finalist_watch_providers(lobby_id: str, force: bool = False) -> int:
    settings = get_settings()
    sessionmaker = get_worker_runtime().sessionmaker
    queued = 0
    with sessionmaker() as session:
        lobby = session.get(Lobby, UUID(lobby_id))
        if lobby is None:
            return 0
        movie_ids = {int(movie_id) for movie_id in (lobby.finalists or [])}
        if lobby.winner_movie_id is not None:
            movie_ids.add(lobby.winner_movie_id)
    for movie_id in movie_ids:
        refresh_movie_watch_providers.delay(movie_id, settings.default_region, force)
        queued += 1
    return queued


@celery_app.task(name="watchlog.watch.prefetch_active_finalists")
def prefetch_active_finalists() -> int:
    sessionmaker = get_worker_runtime().sessionmaker
    with sessionmaker() as session:
        lobby_ids = list(session.scalars(select(Lobby.id).where(Lobby.status == "final_round")))
    for lobby_id in lobby_ids:
        prefetch_finalist_watch_providers.delay(str(lobby_id))
    return len(lobby_ids)
