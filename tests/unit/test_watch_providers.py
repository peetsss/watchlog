from datetime import UTC, datetime

from app.services.watch_providers import build_availability, parse_watch_providers

PAYLOAD = {
    "results": {
        "PL": {
            "link": "https://www.themoviedb.org/movie/1/watch?locale=PL",
            "flatrate": [
                {
                    "provider_id": 8,
                    "provider_name": "Netflix",
                    "logo_path": "/netflix.jpg",
                    "display_priority": 2,
                },
                {
                    "provider_id": 2,
                    "provider_name": "Apple TV",
                    "logo_path": "/apple.jpg",
                    "display_priority": 1,
                },
                {
                    "provider_id": 8,
                    "provider_name": "Netflix",
                    "logo_path": "/netflix.jpg",
                    "display_priority": 2,
                },
            ],
        }
    }
}


def test_parse_watch_providers_groups_and_sorts_offers() -> None:
    parsed = parse_watch_providers(PAYLOAD, "PL")

    assert parsed is not None
    assert parsed.link == "https://www.themoviedb.org/movie/1/watch?locale=PL"
    assert [offer.provider_name for offer in parsed.offers["flatrate"]] == ["Apple TV", "Netflix"]
    assert parsed.offers["rent"] == ()


def test_parse_watch_providers_marks_a_region_without_offers() -> None:
    parsed = parse_watch_providers({"results": {"PL": {"link": None}}}, "PL")

    assert parsed is not None
    assert parsed.link is None
    assert all(not offers for offers in parsed.offers.values())


def test_parse_watch_providers_rejects_an_invalid_payload() -> None:
    assert parse_watch_providers({"results": []}, "PL") is None


def test_build_availability_builds_logo_urls() -> None:
    parsed = parse_watch_providers(PAYLOAD, "PL")
    assert parsed is not None

    availability = build_availability(
        region="PL",
        link=parsed.link,
        fetched_at=datetime.now(UTC),
        offers=parsed.offers,
        stale=False,
    )

    assert availability.offers.flatrate[0].logo_url == "https://image.tmdb.org/t/p/w92/apple.jpg"
    assert availability.offers.rent == []
