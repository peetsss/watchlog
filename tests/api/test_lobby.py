import asyncio
from collections.abc import Callable
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from tests.api.helpers import (
    create_group,
    create_group_lobby,
    create_guest,
    create_lobby,
    csrf_headers,
    current_csrf,
    join_group,
    join_open_lobby,
    lobby_action,
    lobby_state,
    new_client,
    register_member,
)


def insert_movies(movie_factory: Callable[..., int], count: int) -> None:
    for index in range(count):
        movie_factory(tmdb_id=100000 + index, title=f"Movie {index}")


async def test_active_is_null(client: AsyncClient) -> None:
    await register_member(client)

    response = await client.get("/api/lobby/active/")

    assert response.status_code == 200
    assert response.json() == {"active": None}


async def test_guest_can_host_play_and_claim_an_open_lobby(
    client: AsyncClient,
    movie_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 3)
    guest = await create_guest(client, "Riley")
    assert guest["is_guest"] is True
    assert (await client.get("/api/me")).status_code == 401

    lobby = await create_lobby(client)
    assert lobby["players"][0]["is_guest"] is True
    assert lobby["players"][0]["name"] == "Riley"

    ready = await lobby_action(client, lobby["uuid"], "ready")
    assert ready["status"] == "ready"
    playing = await lobby_action(client, lobby["uuid"], "start")
    assert playing["status"] == "playing"

    await register_member(client)
    claimed = await lobby_state(client, lobby["uuid"])

    assert claimed["viewer_id"] == lobby["viewer_id"]
    assert claimed["players"][0]["name"] == "alice"
    assert claimed["players"][0]["is_guest"] is False
    assert claimed["players"][0]["is_host"] is True


async def test_guest_can_join_an_open_lobby(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 2)
    await register_member(client)
    lobby = await create_lobby(client)

    async with new_client(app) as guest_client:
        await create_guest(guest_client, "Riley")
        preview = await guest_client.get(f"/api/lobby/{lobby['uuid']}/preview/")
        assert preview.status_code == 200
        assert preview.json()["preview"]["is_participant"] is False
        assert preview.json()["preview"]["can_join"] is True

        joined = await join_open_lobby(guest_client, lobby["uuid"])
        assert joined["player_count"] == 2
        assert any(player["is_guest"] for player in joined["players"])


async def test_create_state_and_etag(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 3)

    lobby = await create_lobby(client)

    assert lobby["type"] == "open"
    assert lobby["status"] == "ready"
    assert lobby["version"] == 0
    assert lobby["player_count"] == 1
    assert lobby["pool_size"] == 3
    assert lobby["viewer_id"] == lobby["host_id"]
    assert lobby["players"][0]["name"] == "alice"
    assert lobby["players"][0]["is_host"] is True
    assert lobby["capabilities"]["can_start"] is True

    state = await client.get(f"/api/lobby/{lobby['uuid']}/")
    assert state.headers["ETag"] == '"v0"'

    unchanged = await client.get(
        f"/api/lobby/{lobby['uuid']}/",
        headers={"If-None-Match": '"v0"'},
    )
    assert unchanged.status_code == 304

    ready = await lobby_action(client, lobby["uuid"], "ready")
    assert ready["version"] == 1
    changed = await client.get(f"/api/lobby/{lobby['uuid']}/")
    assert changed.headers["ETag"] == '"v1"'

    active = await client.get("/api/lobby/active/")
    assert active.json()["active"]["uuid"] == lobby["uuid"]


async def test_create_rejects_malformed_and_unknown_groups(
    client: AsyncClient,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    insert_movies(movie_factory, 1)
    headers = csrf_headers(current_csrf(client))

    malformed = await client.post("/api/lobby/", json={"group_uuid": "not-a-uuid"}, headers=headers)
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_action"

    unknown = await client.post("/api/lobby/", json={"group_uuid": str(uuid4())}, headers=headers)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "not_found"


async def test_ready_unready_and_start(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    ready = await lobby_action(client, lobby["uuid"], "ready")
    assert ready["viewer_ready"] is True
    assert ready["version"] == 1

    unready = await lobby_action(client, lobby["uuid"], "unready")
    assert unready["viewer_ready"] is False
    assert unready["version"] == 2

    await lobby_action(client, lobby["uuid"], "ready")
    started = await lobby_action(client, lobby["uuid"], "start")

    assert started["status"] == "playing"
    assert started["current_movie"] is not None
    assert started["viewer_is_host"] is True
    assert started["capabilities"]["can_advance"] is True


async def test_non_host_cannot_start(client: AsyncClient, app: FastAPI, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_open_lobby(bob_client, lobby["uuid"])

        response = await bob_client.post(
            f"/api/lobby/{lobby['uuid']}/start/",
            json={},
            headers=csrf_headers(current_csrf(bob_client)),
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_host"


async def test_join_preview_and_join(client: AsyncClient, app: FastAPI, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")

        preview = await bob_client.get(f"/api/lobby/{lobby['uuid']}/preview/")
        assert preview.status_code == 200
        assert preview.json()["preview"]["can_join"] is True
        assert preview.json()["preview"]["is_participant"] is False

        joined = await join_open_lobby(bob_client, lobby["uuid"])
        assert joined["player_count"] == 2

        again = await join_open_lobby(bob_client, lobby["uuid"])
        assert again["player_count"] == 2

        member_preview = await bob_client.get(f"/api/lobby/{lobby['uuid']}/preview/")
        assert member_preview.json()["preview"]["is_participant"] is True
        assert member_preview.json()["preview"]["can_join"] is False


async def test_host_start_removes_unready_members(
    client: AsyncClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_open_lobby(bob_client, lobby["uuid"])

        await lobby_action(client, lobby["uuid"], "ready")
        started = await lobby_action(client, lobby["uuid"], "start")

        assert started["player_count"] == 1
        assert (await bob_client.get(f"/api/lobby/{lobby['uuid']}/")).status_code == 403


async def test_vote_reveal_and_next_round(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 3)
    lobby = await create_lobby(client)
    await lobby_action(client, lobby["uuid"], "ready")
    started = await lobby_action(client, lobby["uuid"], "start")
    current = started["current_movie"]["id"]

    invalid = await client.post(
        f"/api/lobby/{lobby['uuid']}/vote/",
        json={"movie_id": current, "choice": "maybe"},
        headers=csrf_headers(current_csrf(client)),
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_choice"

    revealed = await lobby_action(
        client,
        lobby["uuid"],
        "vote",
        {"movie_id": current, "choice": "interested"},
    )
    assert revealed["revealed"] is True
    assert revealed["vote_tally"] == {"interested": 1, "watched": 0, "not_interested": 0, "total": 1}
    assert revealed["ballot"][0]["name"] == "alice"
    assert revealed["finalists"][0]["movie"]["id"] == current

    again = await client.post(
        f"/api/lobby/{lobby['uuid']}/vote/",
        json={"movie_id": current, "choice": "watched"},
        headers=csrf_headers(current_csrf(client)),
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "invalid_state"

    next_round = await lobby_action(client, lobby["uuid"], "next-round")
    assert next_round["revealed"] is False
    assert next_round["pool_index"] == 1
    assert next_round["round_number"] == 2

    advanced = await lobby_action(client, lobby["uuid"], "advance")
    assert advanced["pool_index"] == 2
    assert advanced["status"] == "playing"


async def test_final_round_and_finalize(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 10)
    lobby = await create_lobby(client)
    await lobby_action(client, lobby["uuid"], "ready")
    lobby = await lobby_action(client, lobby["uuid"], "start")

    while lobby["status"] == "playing":
        current = lobby["current_movie"]["id"]
        lobby = await lobby_action(
            client,
            lobby["uuid"],
            "vote",
            {"movie_id": current, "choice": "interested"},
        )
        assert lobby["revealed"] is True
        lobby = await lobby_action(client, lobby["uuid"], "next-round")

    assert lobby["status"] == "final_round"
    assert len(lobby["finalists"]) == 10
    assert lobby["picks_revealed"] is False
    assert lobby["finalists"][0]["pick_count"] is None

    target = lobby["finalists"][0]["movie"]["id"]
    lobby = await lobby_action(client, lobby["uuid"], "pick", {"movie_id": target})
    assert lobby["picks_revealed"] is True
    assert lobby["finalists"][0]["pick_count"] == 1

    finished = await lobby_action(client, lobby["uuid"], "finalize")
    assert finished["status"] == "finished"
    assert finished["winner"]["id"] == target
    assert finished["capabilities"]["can_restart"] is True


async def test_leave_and_host_leave(client: AsyncClient, app: FastAPI, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_open_lobby(bob_client, lobby["uuid"])

        left = await bob_client.post(
            f"/api/lobby/{lobby['uuid']}/leave/",
            json={},
            headers=csrf_headers(current_csrf(bob_client)),
        )
        assert left.status_code == 204
        assert (await bob_client.get(f"/api/lobby/{lobby['uuid']}/")).status_code == 403

        host_leave = await client.post(
            f"/api/lobby/{lobby['uuid']}/leave/",
            json={},
            headers=csrf_headers(current_csrf(client)),
        )
        assert host_leave.status_code == 403


async def test_end_and_restart(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    ended = await lobby_action(client, lobby["uuid"], "end")
    assert ended["status"] == "finished"

    restarted = await client.post(
        f"/api/lobby/{lobby['uuid']}/restart/",
        json={},
        headers=csrf_headers(current_csrf(client)),
    )
    assert restarted.status_code == 201
    body = restarted.json()
    assert body["previous_uuid"] == lobby["uuid"]
    assert body["lobby"]["uuid"] != lobby["uuid"]
    assert body["lobby"]["status"] == "ready"

    active = await client.get("/api/lobby/active/")
    assert active.json()["active"]["uuid"] == body["lobby"]["uuid"]


async def test_group_lobby_and_privacy(client: AsyncClient, app: FastAPI) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_group(bob_client, group["id"])

        lobby = await create_group_lobby(client, group["id"])
        assert lobby["type"] == "group"
        assert lobby["group_uuid"] == group["id"]
        assert lobby["player_count"] == 2

        duplicate = await client.post(
            "/api/lobby/",
            json={"group_uuid": group["id"]},
            headers=csrf_headers(current_csrf(client)),
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "already_active"

    async with new_client(app) as carol_client:
        await register_member(carol_client, "carol")

        preview = await carol_client.get(f"/api/lobby/{lobby['uuid']}/preview/")
        assert preview.status_code == 403
        assert preview.json()["error"]["code"] == "not_a_member"

        join = await carol_client.post(
            f"/api/lobby/{lobby['uuid']}/join/",
            headers=csrf_headers(current_csrf(carol_client)),
        )
        assert join.status_code == 409
        assert join.json()["error"]["code"] == "not_joinable"

        group_denied = await carol_client.post(
            f"/api/groups/{group['id']}/lobbies",
            headers=csrf_headers(current_csrf(carol_client)),
        )
        assert group_denied.status_code == 403


async def test_group_lobby_winner_is_added_to_the_watchlist(
    client: AsyncClient,
    movie_factory: Callable[..., int],
) -> None:
    await register_member(client)
    group = await create_group(client, "Friday Film Club")
    movie_factory(tmdb_id=100001, title="Winner")
    lobby = await create_group_lobby(client, group["id"])

    await lobby_action(client, lobby["uuid"], "ready")
    started = await lobby_action(client, lobby["uuid"], "start")
    current = started["current_movie"]["id"]
    await lobby_action(client, lobby["uuid"], "vote", {"movie_id": current, "choice": "interested"})
    final = await lobby_action(client, lobby["uuid"], "next-round")
    assert final["status"] == "final_round"

    target = final["finalists"][0]["movie"]["id"]
    await lobby_action(client, lobby["uuid"], "pick", {"movie_id": target})
    finished = await lobby_action(client, lobby["uuid"], "finalize")
    assert finished["status"] == "finished"

    watchlist = await client.get(f"/api/groups/{group['id']}/watchlist")

    assert watchlist.status_code == 200
    films = watchlist.json()["films"]
    assert len(films) == 1
    assert films[0]["movie"]["id"] == target


async def test_invalid_action_and_malformed_json(client: AsyncClient, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 1)
    lobby = await create_lobby(client)

    unknown = await client.post(
        f"/api/lobby/{lobby['uuid']}/dance/",
        json={},
        headers=csrf_headers(current_csrf(client)),
    )
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "invalid_action"

    malformed = await client.post(
        f"/api/lobby/{lobby['uuid']}/ready/",
        content="{not json",
        headers={**csrf_headers(current_csrf(client)), "Content-Type": "application/json"},
    )
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_action"


async def test_concurrent_votes(client: AsyncClient, app: FastAPI, movie_factory: Callable[..., int]) -> None:
    await register_member(client)
    insert_movies(movie_factory, 2)
    lobby = await create_lobby(client)

    async with new_client(app) as bob_client:
        await register_member(bob_client, "bob")
        await join_open_lobby(bob_client, lobby["uuid"])
        await lobby_action(client, lobby["uuid"], "ready")
        await lobby_action(bob_client, lobby["uuid"], "ready")
        started = await lobby_action(client, lobby["uuid"], "start")
        current = started["current_movie"]["id"]

        await asyncio.gather(
            lobby_action(client, lobby["uuid"], "vote", {"movie_id": current, "choice": "interested"}),
            lobby_action(bob_client, lobby["uuid"], "vote", {"movie_id": current, "choice": "watched"}),
        )

    state = await lobby_state(client, lobby["uuid"])

    assert state["revealed"] is True
    assert state["vote_tally"]["total"] == 2
    assert len(state["ballot"]) == 2
    assert state["submitted_count"] == 2


async def test_unauthenticated_lobby_requests(client: AsyncClient) -> None:
    response = await client.get("/api/lobby/active/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
