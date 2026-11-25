import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.clients.tmdb import SyncTMDBClient  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.catalog import (  # noqa: E402
    CatalogueImportStats,
    discover_window,
    iter_month_windows,
    latest_catalogue_date,
    sync_catalogue_range,
)

DEFAULT_MAX_PAGES = 500
DEFAULT_MAX_REQUESTS = 10_000


class BudgetClient:
    def __init__(self, client: SyncTMDBClient, budget: int) -> None:
        self._client = client
        self._budget = budget
        self.used = 0
        self.exhausted = False

    def discover(self, media_type: str, start: date, end: date, page: int = 1) -> dict[str, object] | None:
        if self.exhausted:
            return None
        self.used += 1
        self.exhausted = self.used >= self._budget
        return self._client.discover(media_type, start, end, page)

    def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        if self.exhausted:
            return None
        self.used += 1
        self.exhausted = self.used >= self._budget
        return self._client.get_details(tmdb_id, media_type)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill the movie catalogue from TMDB.")
    parser.add_argument("--media-type", choices=("movie", "series"), default="movie")
    parser.add_argument("--since", type=date.fromisoformat, default=None)
    parser.add_argument("--until", type=date.fromisoformat, default=None)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_MAX_REQUESTS,
        help="stop after this many API requests; run again to continue",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _resolve_window(session: Session, media_type: str, args: argparse.Namespace) -> tuple[date, date] | None:
    until = args.until or datetime.now(UTC).date()
    since = args.since
    if since is None:
        newest = latest_catalogue_date(session, media_type)
        if newest is None:
            raise SystemExit(f"no {media_type} catalogue rows found; pass --since or import the CSV dataset first")
        since = newest + timedelta(days=1)
    if since > until:
        return None
    return since, until


def _print_month_stats(start: date, end: date, stats: CatalogueImportStats) -> None:
    print(
        f"{start}..{end}: discovered={stats.discovered} inserted={stats.inserted} "
        f"updated={stats.updated} skipped={stats.skipped} failed={stats.failed}"
    )


def main() -> None:
    args = build_parser().parse_args()

    settings = Settings()
    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    with SyncTMDBClient(
        api_key=settings.tmdb_api_key.get_secret_value(),
        access_token=settings.tmdb_access_token.get_secret_value(),
        language=settings.tmdb_language,
        requests_per_second=settings.tmdb_rate_limit_per_second,
    ) as client:
        budgeted = BudgetClient(client, args.max_requests)

        with Session(engine) as session:
            window = _resolve_window(session, args.media_type, args)
            if window is None:
                print(f"{args.media_type} catalogue is up to date; nothing to backfill")
                return
            since, until = window
            print(f"backfilling {args.media_type} catalogue from {since} to {until}")
            if args.dry_run:
                for start, end in iter_month_windows(since, until):
                    if budgeted.exhausted:
                        break
                    discovered = discover_window(budgeted, args.media_type, start, end, args.max_pages)
                    if discovered is None:
                        print(f"{start}..{end}: discovery unavailable")
                        continue
                    suffix = "" if discovered.complete else " (incomplete)"
                    print(f"{start}..{end}: {len(discovered.results)} results{suffix}")
                if budgeted.exhausted:
                    print(f"requests budget exhausted after {budgeted.used} requests; run again to continue")
                return

            for start, end in iter_month_windows(since, until):
                if budgeted.exhausted:
                    break
                stats = sync_catalogue_range(
                    session,
                    budgeted,
                    args.media_type,
                    start,
                    end,
                    max_pages=args.max_pages,
                    refresh_existing=False,
                )
                _print_month_stats(start, end, stats)
                if budgeted.exhausted:
                    print(f"requests budget exhausted after {budgeted.used} requests; run again to continue")
                    break


if __name__ == "__main__":
    main()
