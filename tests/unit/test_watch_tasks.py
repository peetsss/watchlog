import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.group import Group, GroupMovie
from app.models.lobby import Lobby
from app.models.movie import Movie
from app.models.watch import MovieWatchProvider, MovieWatchRegion
from app.tasks.watch_providers import (
    prefetch_finalist_watch_providers,
    refresh_movie_watch_providers,
    refresh_stale_watch_providers,
)
from app.workers.runtime import dispose_worker_runtime, init_worker_runtime

WATCH_PAYLOAD = {
    "results": {
        "PL": {
            "link": "https://www.themoviedb.org/movie/1/watch?locale=PL",
            "flatrate": [
                {
                    "provider_id": 8,
                    "provider_name": "Netflix",
                    "logo_path": "/netflix.jpg",
                    "display_priority": 1,
                }
            ],
        }
    }
}


class FakeWatchClient:
    def __enter__(self) -> FakeWatchClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get_watch_providers(self, tmdb_id: int, media_type: str) -> dict[str, object]:
        return WATCH_PAYLOAD


def _movie(session: Session, tmdb_id: int = 501) -> Movie:
    movie = Movie(tmdb_id=tmdb_id, title="Dune", media_type="movie")
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def test_refresh_movie_watch_providers_upserts_snapshot(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    movie = _movie(sync_session)
    monkeypatch.setattr("app.tasks.watch_providers.SyncTMDBWatchProviderClient", lambda **_: FakeWatchClient())
    init_worker_runtime(test_settings)

    try:
        result = refresh_movie_watch_providers.apply(args=[movie.id, "PL", True]).get()
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    region_row = sync_session.get(MovieWatchRegion, (movie.id, "PL"))
    providers = list(sync_session.scalars(select(MovieWatchProvider).where(MovieWatchProvider.movie_id == movie.id)))
    assert result is True
    assert region_row is not None
    assert region_row.offer_count == 1
    assert providers[0].provider_name == "Netflix"


def test_prefetch_finalists_enqueues_each_movie(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    movie = _movie(sync_session)
    lobby = Lobby(type="open", status="final_round", pool=[], finalists=[movie.id], version=0)
    sync_session.add(lobby)
    sync_session.commit()
    enqueued: list[tuple[int, str, bool]] = []
    monkeypatch.setattr(
        "app.tasks.watch_providers.refresh_movie_watch_providers.delay",
        lambda movie_id, region, force=False: enqueued.append((movie_id, region, force)),
    )
    init_worker_runtime(test_settings)

    try:
        result = prefetch_finalist_watch_providers.apply(args=[str(lobby.id), True]).get()
    finally:
        dispose_worker_runtime()

    assert result == 1
    assert enqueued == [(movie.id, "PL", True)]


def test_stale_refresh_enqueues_watchlist_movies(
    sync_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    movie = _movie(sync_session)
    group = Group(name="Friday Film Club")
    sync_session.add(group)
    sync_session.flush()
    sync_session.add(GroupMovie(group_id=group.id, movie_id=movie.id))
    sync_session.commit()
    enqueued: list[int] = []
    monkeypatch.setattr(
        "app.tasks.watch_providers.refresh_movie_watch_providers.delay",
        lambda movie_id, region: enqueued.append(movie_id),
    )
    init_worker_runtime(test_settings)

    try:
        result = refresh_stale_watch_providers.apply().get()
    finally:
        dispose_worker_runtime()

    assert result == 1
    assert enqueued == [movie.id]
