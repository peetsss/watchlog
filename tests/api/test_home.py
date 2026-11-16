from datetime import date

from fastapi import FastAPI
from httpx import AsyncClient

from tests.api.helpers import (
    add_film,
    create_group,
    create_group_lobby,
    new_client,
    register_member,
    score_film,
)


async def test_home_is_empty_without_groups(client: AsyncClient) -> None:
    viewer = await register_member(client)

    response = await client.get("/api/home")

    assert response.status_code == 200
    payload = response.json()
    assert payload["viewer"]["id"] == viewer["id"]
    assert payload["viewer"]["username"] == "alice"
    assert payload["active_lobby"] is None
    assert payload["crews"] == {"count": 0, "film_count": 0, "watched_count": 0}
    assert payload["featured_group"] is None
    assert payload["log"] == []


async def test_home_derives_the_featured_group_and_log(client: AsyncClient, movie_factory) -> None:
    movie_factory(
        tmdb_id=27205,
        title="Inception",
        release_date=date(2010, 7, 15),
        runtime=148,
        genres="Action, Science Fiction",
        description="Cobb steals ideas from dreams.",
        poster_path="https://image.tmdb.org/t/p/w500/inception.jpg",
    )
    movie_factory(
        tmdb_id=157336,
        title="Interstellar",
        release_date=date(2014, 11, 5),
        runtime=169,
        genres="Adventure, Drama",
        description="Explorers travel through a wormhole.",
    )
    await register_member(client)
    group = await create_group(client, "Friday Film Club", "A weekly film club.")

    watched = await add_film(client, group["id"], 27205)
    upcoming = await add_film(client, group["id"], 157336)
    await score_film(client, group["id"], watched["id"], 8.0)
    lobby = await create_group_lobby(client, group["id"])

    response = await client.get("/api/home")

    assert response.status_code == 200
    payload = response.json()
    assert payload["crews"] == {"count": 1, "film_count": 2, "watched_count": 1}
    assert payload["active_lobby"]["uuid"] == lobby["uuid"]
    assert payload["active_lobby"]["group_name"] == "Friday Film Club"

    featured = payload["featured_group"]
    assert featured["id"] == group["id"]
    assert featured["name"] == "Friday Film Club"
    assert featured["member_count"] == 1
    assert featured["film_count"] == 2
    assert featured["up_next_count"] == 1
    assert featured["up_next"][0]["id"] == upcoming["movie"]["id"]
    assert featured["last_watched"]["film_id"] == watched["id"]
    assert featured["last_watched"]["club_score"] == 8.0
    assert featured["last_watched"]["score_count"] == 1

    assert len(payload["log"]) == 1
    entry = payload["log"][0]
    assert entry["film_id"] == watched["id"]
    assert entry["group_name"] == "Friday Film Club"
    assert entry["movie"]["title"] == "Inception"
    assert entry["club_score"] == 8.0
    assert entry["score_count"] == 1


async def test_home_does_not_leak_other_groups(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    await create_group(client, "Friday Film Club")

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        response = await bob_client.get("/api/home")

        assert response.status_code == 200
        assert response.json()["crews"]["count"] == 0
        assert response.json()["featured_group"] is None
        assert response.json()["log"] == []
