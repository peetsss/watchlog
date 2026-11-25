from datetime import date

from scripts.sync_catalog import BudgetClient, build_parser


class FakeClient:
    def discover(self, media_type: str, start: date, end: date, page: int = 1) -> dict[str, object]:
        return {"total_pages": 1, "results": []}

    def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object]:
        return {"id": tmdb_id, "title": "A Film"}


def test_budget_client_stops_after_the_budget() -> None:
    client = BudgetClient(FakeClient(), budget=2)

    assert client.discover("movie", date(2026, 1, 1), date(2026, 1, 2)) is not None
    assert client.get_details(1, "movie") is not None
    assert client.used == 2
    assert client.exhausted is True
    assert client.discover("movie", date(2026, 1, 1), date(2026, 1, 2)) is None
    assert client.get_details(2, "movie") is None
    assert client.used == 2


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])

    assert args.media_type == "movie"
    assert args.since is None
    assert args.until is None
    assert args.max_pages == 500
    assert args.max_requests == 10_000
    assert args.dry_run is False
