from collections.abc import Callable
from datetime import date
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_tmdb_client
from tests.api.helpers import (
    add_film,
    create_group,
    csrf_headers,
    current_csrf,
    join_group,
    new_client,
    register_member,
    score_film,
    set_film_status,
)


class FailingTMDB:
    async def get_details(self, tmdb_id: int, media_type: str) -> dict[str, object] | None:
        return None


async def test_empty_group_list(client: AsyncClient) -> None:
    await register_member(client)

    response = await client.get("/api/groups")

    assert response.status_code == 200
    assert response.json() == {"groups": []}


async def test_create_and_list_group(client: AsyncClient) -> None:
    viewer = await register_member(client)

    group = await create_group(client, "Friday Film Club", "Weekly picks")

    assert group["name"] == "Friday Film Club"
    assert group["description"] == "Weekly picks"
    assert group["member_count"] == 1
    assert group["film_count"] == 0
    assert group["members"][0]["id"] == viewer["id"]
    assert group["members"][0]["role"] == "admin"

    response = await client.get("/api/groups")
    groups = response.json()["groups"]

    assert len(groups) == 1
    assert groups[0]["id"] == group["id"]
    assert groups[0]["member_count"] == 1


async def test_create_group_validates_the_name(client: AsyncClient) -> None:
    await register_member(client)

    for name in ("", "   "):
        response = await client.post(
            "/api/groups",
            json={"name": name},
            headers=csrf_headers(current_csrf(client)),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"


async def test_join_and_leave_group(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")

        joined = await join_group(bob_client, group["id"])
        assert joined["member_count"] == 2

        again = await join_group(bob_client, group["id"])
        assert again["member_count"] == 2

        detail = await bob_client.get(f"/api/groups/{group['id']}")
        assert detail.status_code == 200
        assert detail.json()["member_count"] == 2

        left = await bob_client.delete(
            f"/api/groups/{group['id']}/members/me",
            headers=csrf_headers(current_csrf(bob_client)),
        )
        assert left.status_code == 204
        assert (await bob_client.get(f"/api/groups/{group['id']}")).status_code == 403

    detail = await client.get(f"/api/groups/{group['id']}")
    assert detail.json()["member_count"] == 1


async def test_group_preview(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club", "Weekly picks")

    response = await client.get(f"/api/groups/{group['id']}/preview")
    assert response.status_code == 200
    assert response.json() == {
        "id": group["id"],
        "name": "Friday Film Club",
        "description": "Weekly picks",
        "member_count": 1,
        "film_count": 0,
        "is_member": True,
    }

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")

        preview = await bob_client.get(f"/api/groups/{group['id']}/preview")
        assert preview.status_code == 200
        assert preview.json()["is_member"] is False
        assert preview.json()["member_count"] == 1

    missing = await client.get(f"/api/groups/{uuid4()}/preview")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


async def test_non_members_are_forbidden(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")

        for path in (
            f"/api/groups/{group['id']}",
            f"/api/groups/{group['id']}/watchlist",
            f"/api/groups/{group['id']}/stats",
            f"/api/groups/{group['id']}/invite",
        ):
            response = await bob_client.get(path)
            assert response.status_code == 403, path
            assert response.json()["error"]["code"] == "not_a_member"

        add = await bob_client.post(
            f"/api/groups/{group['id']}/films",
            json={"tmdb_id": 1, "media_type": "movie"},
            headers=csrf_headers(current_csrf(bob_client)),
        )
        assert add.status_code == 403

        score = await bob_client.put(
            f"/api/groups/{group['id']}/films/1/score",
            json={"score": 8},
            headers=csrf_headers(current_csrf(bob_client)),
        )
        assert score.status_code == 403

        leave = await bob_client.delete(
            f"/api/groups/{group['id']}/members/me",
            headers=csrf_headers(current_csrf(bob_client)),
        )
        assert leave.status_code == 403


async def test_unknown_group_is_not_found(client: AsyncClient) -> None:
    await register_member(client)

    response = await client.get(f"/api/groups/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_add_film_is_idempotent(
    client: AsyncClient,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_id = movie_factory(
        tmdb_id=27205,
        title="Inception",
        release_date=date(2010, 7, 15),
        runtime=148,
    )

    film = await add_film(client, group["id"], 27205)

    assert film["movie"]["id"] == movie_id
    assert film["movie"]["title"] == "Inception"
    assert film["status"] == "up_next"
    assert film["club_score"] is None
    assert film["score_count"] == 0
    assert film["your_score"] is None
    assert film["added_by"] == "alice"

    again = await add_film(client, group["id"], 27205)
    assert again["id"] == film["id"]

    watchlist = await client.get(f"/api/groups/{group['id']}/watchlist")
    assert watchlist.status_code == 200
    assert len(watchlist.json()["films"]) == 1


async def test_scores_and_the_watched_rule(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_factory(tmdb_id=27205, title="Inception")
    film = await add_film(client, group["id"], 27205)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_group(bob_client, group["id"])

        alice = await score_film(client, group["id"], film["id"], 8.0)
        assert alice["club_score"] == 8.0
        assert alice["score_count"] == 1
        assert alice["your_score"] == 8.0
        assert alice["status"] == "up_next"

        bob = await score_film(bob_client, group["id"], film["id"], 7.0)
        assert bob["club_score"] == 7.5
        assert bob["score_count"] == 2
        assert bob["your_score"] == 7.0
        assert bob["status"] == "watched"

        scores = await client.get(f"/api/groups/{group['id']}/films/{film['id']}/scores")
        assert scores.status_code == 200
        assert [entry["username"] for entry in scores.json()["scores"]] == ["alice", "bob"]
        assert [entry["score"] for entry in scores.json()["scores"]] == [8.0, 7.0]

        stats = await client.get(f"/api/groups/{group['id']}/stats")
        assert stats.status_code == 200
        body = stats.json()
        assert body["film_count"] == 1
        assert body["watched_count"] == 1
        assert body["up_next_count"] == 0
        assert body["member_count"] == 2
        assert body["average_score"] == 7.5
        assert len(body["member_scores"]) == 2

        reset = await set_film_status(client, group["id"], film["id"], "up_next")
        assert reset["status"] == "up_next"

        me = await client.get("/api/me")
        assert me.json()["stats"] == {"titles_watched": 1, "average_score": 8.0}


async def test_club_score_rounds_half_up(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_factory(tmdb_id=27205, title="Inception")
    film = await add_film(client, group["id"], 27205)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_group(bob_client, group["id"])
        await score_film(client, group["id"], film["id"], 8.5)
        scored = await score_film(bob_client, group["id"], film["id"], 8.0)

    assert scored["club_score"] == 8.3

    stats = await client.get(f"/api/groups/{group['id']}/stats")
    assert stats.json()["average_score"] == 8.3


async def test_all_three_members_must_score(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_factory(tmdb_id=27205, title="Inception")
    film = await add_film(client, group["id"], 27205)

    async with new_client(app) as bob_client, new_client(app) as carol_client:
        await register_member(bob_client, "bob")
        await register_member(carol_client, "carol")
        await join_group(bob_client, group["id"])
        await join_group(carol_client, group["id"])

        await score_film(client, group["id"], film["id"], 8.0)
        after_two = await score_film(bob_client, group["id"], film["id"], 7.0)
        assert after_two["status"] == "up_next"
        assert after_two["score_count"] == 2

        after_three = await score_film(carol_client, group["id"], film["id"], 9.0)
        assert after_three["status"] == "watched"
        assert after_three["score_count"] == 3
        assert after_three["club_score"] == 8.0


async def test_leave_recomputes_the_watched_rule(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_factory(tmdb_id=27205, title="Inception")
    film = await add_film(client, group["id"], 27205)

    async with new_client(app) as bob_client, new_client(app) as carol_client:
        await register_member(bob_client, "bob")
        await register_member(carol_client, "carol")
        await join_group(bob_client, group["id"])
        await join_group(carol_client, group["id"])

        await score_film(client, group["id"], film["id"], 8.0)

        await bob_client.delete(
            f"/api/groups/{group['id']}/members/me",
            headers=csrf_headers(current_csrf(bob_client)),
        )
        watchlist = await client.get(f"/api/groups/{group['id']}/watchlist")
        assert watchlist.json()["films"][0]["status"] == "up_next"

        await carol_client.delete(
            f"/api/groups/{group['id']}/members/me",
            headers=csrf_headers(current_csrf(carol_client)),
        )
        watchlist = await client.get(f"/api/groups/{group['id']}/watchlist")
        assert watchlist.json()["films"][0]["status"] == "watched"


async def test_invite_link(client: AsyncClient) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")

    response = await client.get(f"/api/groups/{group['id']}/invite")

    assert response.status_code == 200
    assert response.json()["invite_link"] == f"http://testserver/join/group/{group['id']}"


async def test_group_stats_when_empty(client: AsyncClient) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")

    response = await client.get(f"/api/groups/{group['id']}/stats")

    assert response.status_code == 200
    assert response.json() == {
        "film_count": 0,
        "watched_count": 0,
        "up_next_count": 0,
        "member_count": 1,
        "average_score": None,
        "member_scores": [],
    }


async def test_score_validation(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_factory(tmdb_id=27205, title="Inception")
    film = await add_film(client, group["id"], 27205)

    for score in (0, 11):
        response = await client.put(
            f"/api/groups/{group['id']}/films/{film['id']}/score",
            json={"score": score},
            headers=csrf_headers(current_csrf(client)),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"


async def test_add_film_reports_tmdb_failure(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    app.dependency_overrides[get_tmdb_client] = lambda: FailingTMDB()

    response = await client.post(
        f"/api/groups/{group['id']}/films",
        json={"tmdb_id": 999999, "media_type": "movie"},
        headers=csrf_headers(current_csrf(client)),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "tmdb_unavailable"
