from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.clients.tmdb import TMDBClient
from app.models.movie import Movie
from app.models.watch import MovieWatchProvider, MovieWatchRegion
from app.schemas.watch import WatchAvailability, WatchOffers, WatchProviderRef

OFFER_TYPES: Final[tuple[str, ...]] = ("flatrate", "free", "ads", "rent", "buy")
WATCH_LOGO_BASE_URL: Final[str] = "https://image.tmdb.org/t/p/w92"


@dataclass(frozen=True)
class ProviderOffer:
    provider_id: int
    provider_name: str
    logo_path: str | None
    display_priority: int


@dataclass(frozen=True)
class ParsedWatchRegion:
    link: str | None
    offers: dict[str, tuple[ProviderOffer, ...]]


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


def parse_watch_providers(payload: Mapping[str, object], region: str) -> ParsedWatchRegion | None:
    results = payload.get("results")
    if not isinstance(results, dict):
        return None
    region_payload = results.get(region)
    if not isinstance(region_payload, dict):
        return ParsedWatchRegion(link=None, offers={})

    offers: dict[str, tuple[ProviderOffer, ...]] = {}
    for offer_type in OFFER_TYPES:
        by_id: dict[int, ProviderOffer] = {}
        for item in _as_list(region_payload.get(offer_type)):
            if not isinstance(item, dict):
                continue
            provider_id = _as_int(item.get("provider_id"))
            provider_name = _as_str(item.get("provider_name"))
            if provider_id is None or provider_name is None:
                continue
            by_id[provider_id] = ProviderOffer(
                provider_id=provider_id,
                provider_name=provider_name,
                logo_path=_as_str(item.get("logo_path")),
                display_priority=_as_int(item.get("display_priority")) or 1000,
            )
        offers[offer_type] = tuple(
            sorted(by_id.values(), key=lambda offer: (offer.display_priority, offer.provider_name.casefold()))
        )
    return ParsedWatchRegion(link=_as_str(region_payload.get("link")), offers=offers)


def _provider_ref(provider: ProviderOffer | MovieWatchProvider) -> WatchProviderRef:
    logo_path = provider.logo_path
    return WatchProviderRef(
        provider_id=provider.provider_id,
        name=provider.provider_name,
        logo_url=f"{WATCH_LOGO_BASE_URL}{logo_path}" if logo_path else None,
        priority=provider.display_priority,
    )


def build_availability(
    *,
    region: str,
    link: str | None,
    fetched_at: datetime | None,
    offers: Mapping[str, tuple[ProviderOffer, ...]],
    stale: bool,
) -> WatchAvailability:
    grouped: dict[str, list[WatchProviderRef]] = {offer_type: [] for offer_type in OFFER_TYPES}
    for offer_type, entries in offers.items():
        if offer_type in grouped:
            grouped[offer_type] = [_provider_ref(entry) for entry in entries]
    return WatchAvailability(
        region=region,
        link=link,
        fetched_at=fetched_at,
        stale=stale,
        offers=WatchOffers(**grouped),
    )


def _is_stale(fetched_at: datetime | None, ttl_seconds: int) -> bool:
    if fetched_at is None:
        return True
    return fetched_at < datetime.now(UTC) - timedelta(seconds=ttl_seconds)


async def load_cached_availability(
    db: AsyncSession,
    movie_ids: set[int],
    region: str,
    ttl_seconds: int,
) -> dict[int, WatchAvailability]:
    if not movie_ids:
        return {}
    regions = list(
        await db.scalars(
            select(MovieWatchRegion).where(
                MovieWatchRegion.movie_id.in_(movie_ids),
                MovieWatchRegion.region == region,
            )
        )
    )
    providers = list(
        await db.scalars(
            select(MovieWatchProvider).where(
                MovieWatchProvider.movie_id.in_(movie_ids),
                MovieWatchProvider.region == region,
            )
        )
    )
    offers_by_movie: dict[int, dict[str, list[ProviderOffer]]] = {}
    for provider in providers:
        entry = ProviderOffer(
            provider_id=provider.provider_id,
            provider_name=provider.provider_name,
            logo_path=provider.logo_path,
            display_priority=provider.display_priority,
        )
        offers_by_movie.setdefault(provider.movie_id, {}).setdefault(provider.offer_type, []).append(entry)

    result: dict[int, WatchAvailability] = {}
    for row in regions:
        raw_offers = offers_by_movie.get(row.movie_id, {})
        grouped = {
            offer_type: tuple(
                sorted(entries, key=lambda entry: (entry.display_priority, entry.provider_name.casefold()))
            )
            for offer_type, entries in raw_offers.items()
        }
        result[row.movie_id] = build_availability(
            region=region,
            link=row.tmdb_link,
            fetched_at=row.fetched_at,
            offers=grouped,
            stale=_is_stale(row.fetched_at, ttl_seconds),
        )
    return result


async def _upsert_async(
    db: AsyncSession,
    movie_id: int,
    region: str,
    parsed: ParsedWatchRegion,
) -> WatchAvailability:
    now = datetime.now(UTC)
    row = await db.get(MovieWatchRegion, (movie_id, region))
    if row is None:
        row = MovieWatchRegion(movie_id=movie_id, region=region)
        db.add(row)
    row.tmdb_link = parsed.link
    row.fetched_at = now
    row.last_attempt_at = now
    row.last_error = None
    count = sum(len(entries) for entries in parsed.offers.values())
    row.offer_count = count
    await db.flush()
    await db.execute(
        delete(MovieWatchProvider).where(
            MovieWatchProvider.movie_id == movie_id,
            MovieWatchProvider.region == region,
        )
    )
    for offer_type, entries in parsed.offers.items():
        for offer in entries:
            db.add(
                MovieWatchProvider(
                    movie_id=movie_id,
                    region=region,
                    offer_type=offer_type,
                    provider_id=offer.provider_id,
                    provider_name=offer.provider_name,
                    logo_path=offer.logo_path,
                    display_priority=offer.display_priority,
                )
            )
    return build_availability(
        region=region,
        link=parsed.link,
        fetched_at=now,
        offers=parsed.offers,
        stale=False,
    )


async def get_watch_availability(
    db: AsyncSession,
    movie: Movie,
    region: str,
    settings_ttl_seconds: int,
    tmdb: TMDBClient,
    *,
    refresh: bool = True,
) -> WatchAvailability | None:
    cached = await load_cached_availability(db, {movie.id}, region, settings_ttl_seconds)
    existing = cached.get(movie.id)
    if existing is not None and not existing.stale:
        return existing
    if not refresh or movie.tmdb_id is None:
        return existing

    payload = await tmdb.get_watch_providers(movie.tmdb_id, movie.media_type)
    parsed = parse_watch_providers(payload, region) if payload is not None else None
    if parsed is None:
        if existing is not None:
            row = await db.get(MovieWatchRegion, (movie.id, region))
            if row is not None:
                row.last_attempt_at = datetime.now(UTC)
                row.last_error = "TMDB unavailable"
                await db.commit()
            return existing
        return None
    availability = await _upsert_async(db, movie.id, region, parsed)
    await db.commit()
    return availability


def upsert_watch_region_sync(
    session: Session,
    movie_id: int,
    region: str,
    parsed: ParsedWatchRegion,
) -> None:
    now = datetime.now(UTC)
    row = session.get(MovieWatchRegion, (movie_id, region))
    if row is None:
        row = MovieWatchRegion(movie_id=movie_id, region=region)
        session.add(row)
    row.tmdb_link = parsed.link
    row.fetched_at = now
    row.last_attempt_at = now
    row.last_error = None
    row.offer_count = sum(len(entries) for entries in parsed.offers.values())
    session.flush()
    session.execute(
        delete(MovieWatchProvider).where(
            MovieWatchProvider.movie_id == movie_id,
            MovieWatchProvider.region == region,
        )
    )
    for offer_type, entries in parsed.offers.items():
        for offer in entries:
            session.add(
                MovieWatchProvider(
                    movie_id=movie_id,
                    region=region,
                    offer_type=offer_type,
                    provider_id=offer.provider_id,
                    provider_name=offer.provider_name,
                    logo_path=offer.logo_path,
                    display_priority=offer.display_priority,
                )
            )
