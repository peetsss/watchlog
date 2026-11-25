import logging
from datetime import UTC, datetime, timedelta

from app.celery_app import celery_app
from app.clients.tmdb import SyncTMDBClient
from app.core.config import get_settings
from app.services.catalog import MediaType, sync_catalogue_range
from app.workers.runtime import get_worker_runtime

logger = logging.getLogger(__name__)


def _sync_recent(media_type: MediaType) -> dict[str, int]:
    settings = get_settings()
    sessionmaker = get_worker_runtime().sessionmaker
    today = datetime.now(UTC).date()
    start = today - timedelta(days=settings.tmdb_sync_lookback_days)
    with SyncTMDBClient(
        api_key=settings.tmdb_api_key.get_secret_value(),
        access_token=settings.tmdb_access_token.get_secret_value(),
        language=settings.tmdb_language,
        requests_per_second=settings.tmdb_rate_limit_per_second,
    ) as client:
        with sessionmaker() as session:
            stats = sync_catalogue_range(
                session,
                client,
                media_type,
                start,
                today,
                max_pages=settings.tmdb_sync_max_pages,
                refresh_existing=True,
                min_votes=settings.tmdb_sync_min_vote_count,
            )
    logger.info(
        "TMDB catalogue sync for %s: discovered=%s inserted=%s updated=%s skipped=%s failed=%s",
        media_type,
        stats.discovered,
        stats.inserted,
        stats.updated,
        stats.skipped,
        stats.failed,
    )
    return stats.to_dict()


@celery_app.task(name="watchlog.catalog.sync_recent_movies")
def sync_recent_movies() -> dict[str, int]:
    return _sync_recent("movie")


@celery_app.task(name="watchlog.catalog.sync_recent_series")
def sync_recent_series() -> dict[str, int]:
    return _sync_recent("series")
