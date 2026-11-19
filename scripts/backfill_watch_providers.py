import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.clients.tmdb import SyncTMDBWatchProviderClient  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.models.group import GroupMovie  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.models.watch import MovieWatchRegion  # noqa: E402
from app.services.watch_providers import parse_watch_providers, upsert_watch_region_sync  # noqa: E402


def _movies(session: Session, scope: str, limit: int) -> list[Movie]:
    statement = select(Movie).where(Movie.tmdb_id.is_not(None), Movie.adult.is_(False))
    if scope == "watchlists":
        statement = statement.join(GroupMovie, GroupMovie.movie_id == Movie.id).distinct()
    elif scope == "popular":
        statement = statement.order_by(Movie.popularity.desc().nullslast(), Movie.id)
    elif scope == "all":
        statement = statement.order_by(Movie.id)
    else:
        raise SystemExit(f"Unknown scope: {scope}")
    return list(session.scalars(statement.limit(limit)))


def _fresh_region(session: Session, movie_id: int, region: str, ttl_seconds: int) -> bool:
    row = session.get(MovieWatchRegion, (movie_id, region))
    if row is None or row.fetched_at is None:
        return False
    return row.fetched_at >= datetime.now(UTC) - timedelta(seconds=ttl_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill TMDB/JustWatch availability into Postgres.")
    parser.add_argument("--region", default=None)
    parser.add_argument("--scope", choices=("watchlists", "popular", "all"), default="watchlists")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    region = args.region or settings.default_region
    api_key = settings.tmdb_api_key.get_secret_value()
    access_token = settings.tmdb_access_token.get_secret_value()

    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    with Session(engine) as session:
        movies = _movies(session, args.scope, args.limit)
        if args.dry_run:
            print(f"dry run: {len(movies)} movies in scope={args.scope} region={region}")
            for movie in movies[:10]:
                print(f"  {movie.tmdb_id} {movie.title}")
            return

        if not api_key and not access_token:
            raise SystemExit("TMDB_ACCESS_TOKEN or TMDB_API_KEY is required")

        updated = skipped = failed = 0
        with SyncTMDBWatchProviderClient(
            api_key=api_key,
            access_token=access_token,
            language=settings.tmdb_language,
        ) as client:
            for index, movie in enumerate(movies, start=1):
                if movie.tmdb_id is None:
                    continue
                if not args.force and _fresh_region(session, movie.id, region, settings.watch_provider_ttl_seconds):
                    skipped += 1
                    continue
                payload = client.get_watch_providers(movie.tmdb_id, movie.media_type)
                parsed = parse_watch_providers(payload, region) if payload is not None else None
                if parsed is None:
                    failed += 1
                    print(f"failed: {movie.tmdb_id} {movie.title}")
                    continue
                upsert_watch_region_sync(session, movie.id, region, parsed)
                session.commit()
                updated += 1
                if index % 50 == 0:
                    print(f"processed {index}/{len(movies)}; updated={updated} skipped={skipped} failed={failed}")

    print(f"done: updated={updated} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
