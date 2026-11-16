import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient, WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.core.sessions import new_session
from tests.conftest import _database_url


def csrf_token(client: TestClient) -> str:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def current_csrf(client: TestClient) -> str:
    token = client.cookies.get("wl_csrf")
    assert token
    return token


def register(client: TestClient, username: str) -> str:
    token = csrf_token(client)
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "correct horse"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    session_id = client.cookies.get("wl_session")
    assert session_id
    return session_id


def create_lobby(client: TestClient) -> dict:
    response = client.post("/api/lobby/", json={}, headers={"X-CSRF-Token": current_csrf(client)})
    assert response.status_code == 201
    return response.json()["lobby"]


def lobby_action(client: TestClient, lobby_id: str, action: str) -> dict:
    response = client.post(
        f"/api/lobby/{lobby_id}/{action}/",
        json={},
        headers={"X-CSRF-Token": current_csrf(client)},
    )
    assert response.status_code == 200
    return response.json()["lobby"]


def add_participant(test_database: Settings, lobby_id: str, user_id: int, username: str) -> None:
    with psycopg.connect(_database_url(test_database), autocommit=True) as connection:
        connection.execute(
            "INSERT INTO lobby_participants (id, lobby_id, user_id, display_name) VALUES (%s, %s, %s, %s)",
            (uuid4(), UUID(lobby_id), user_id, username),
        )
        connection.execute("UPDATE lobbies SET version = version + 1 WHERE id = %s", (UUID(lobby_id),))


def member_session(app: FastAPI, user_id: int) -> str:
    data = new_session("member", user_id=user_id)
    return asyncio.run(app.state.session_store.create(data, 3600))


def websocket_for(
    client: TestClient,
    lobby_id: str,
    session_id: str,
    origin: str | None = None,
) -> WebSocketTestSession:
    headers = {"origin": origin} if origin is not None else {}
    return client.websocket_connect(
        f"/ws/lobby/{lobby_id}/",
        cookies={"wl_session": session_id},
        headers=headers,
    )


def insert_movies(movie_factory: Callable[..., int], count: int) -> None:
    for index in range(count):
        movie_factory(tmdb_id=200000 + index, title=f"WebSocket Movie {index}")


def test_two_connections_receive_state(
    ws_client: TestClient,
    app: FastAPI,
    test_database: Settings,
    movie_factory: Callable[..., int],
    user_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 2)
    alice_session = register(ws_client, "alice")
    lobby = create_lobby(ws_client)
    bob_id = user_factory("bob")
    add_participant(test_database, lobby["uuid"], bob_id, "bob")
    bob_session = member_session(app, bob_id)

    with (
        websocket_for(ws_client, lobby["uuid"], alice_session) as alice_ws,
        websocket_for(ws_client, lobby["uuid"], bob_session) as bob_ws,
    ):
        alice_state = alice_ws.receive_json()
        bob_state = bob_ws.receive_json()
        assert alice_state["type"] == "lobby.state"
        assert alice_state["lobby"]["viewer_is_host"] is True
        assert bob_state["lobby"]["viewer_is_host"] is False

        bob_ws.send_json({"action": "ready"})
        alice_ready = alice_ws.receive_json()
        bob_ready = bob_ws.receive_json()

        assert alice_ready["type"] == "lobby.state"
        assert alice_ready["lobby"]["ready_count"] == 1
        assert alice_ready["lobby"]["viewer_ready"] is False
        assert bob_ready["lobby"]["viewer_ready"] is True


def test_leave_sends_left_and_closes(
    ws_client: TestClient,
    app: FastAPI,
    test_database: Settings,
    movie_factory: Callable[..., int],
    user_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 2)
    register(ws_client, "alice")
    lobby = create_lobby(ws_client)
    bob_id = user_factory("bob")
    add_participant(test_database, lobby["uuid"], bob_id, "bob")
    bob_session = member_session(app, bob_id)

    with websocket_for(ws_client, lobby["uuid"], bob_session) as bob_ws:
        bob_ws.receive_json()
        bob_ws.send_json({"action": "leave"})
        left = bob_ws.receive_json()

        assert left == {"type": "lobby.left"}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            bob_ws.receive_json()
        assert exc_info.value.code == 4000


def test_restart_sends_restarted_and_closes(
    ws_client: TestClient,
    movie_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 2)
    alice_session = register(ws_client, "alice")
    lobby = create_lobby(ws_client)

    with websocket_for(ws_client, lobby["uuid"], alice_session) as alice_ws:
        alice_ws.receive_json()
        alice_ws.send_json({"action": "end"})
        ended = alice_ws.receive_json()
        assert ended["lobby"]["status"] == "finished"

        alice_ws.send_json({"action": "restart"})
        restarted = alice_ws.receive_json()

        assert restarted["type"] == "lobby.restarted"
        assert restarted["previous_uuid"] == lobby["uuid"]
        assert restarted["new_lobby_uuid"] != lobby["uuid"]
        with pytest.raises(WebSocketDisconnect) as exc_info:
            alice_ws.receive_json()
        assert exc_info.value.code == 4001


def test_unauthorized_socket_is_closed(ws_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(f"/ws/lobby/{uuid4()}/"):
            pass

    assert exc_info.value.code == 4401


def test_unknown_lobby_is_closed(
    ws_client: TestClient,
    movie_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 1)
    alice_session = register(ws_client, "alice")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with websocket_for(ws_client, str(uuid4()), alice_session):
            pass

    assert exc_info.value.code == 4404


def test_non_member_is_closed(
    ws_client: TestClient,
    app: FastAPI,
    movie_factory: Callable[..., int],
    user_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 1)
    register(ws_client, "alice")
    lobby = create_lobby(ws_client)
    bob_id = user_factory("bob")
    bob_session = member_session(app, bob_id)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with websocket_for(ws_client, lobby["uuid"], bob_session):
            pass

    assert exc_info.value.code == 4403


def test_bad_origin_is_closed(
    ws_client: TestClient,
    movie_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 1)
    alice_session = register(ws_client, "alice")
    lobby = create_lobby(ws_client)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with websocket_for(ws_client, lobby["uuid"], alice_session, origin="http://evil.example"):
            pass

    assert exc_info.value.code == 4403


def test_removed_member_is_notified_and_closed(
    ws_client: TestClient,
    app: FastAPI,
    test_database: Settings,
    movie_factory: Callable[..., int],
    user_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 2)
    register(ws_client, "alice")
    lobby = create_lobby(ws_client)
    bob_id = user_factory("bob")
    add_participant(test_database, lobby["uuid"], bob_id, "bob")
    bob_session = member_session(app, bob_id)

    with websocket_for(ws_client, lobby["uuid"], bob_session) as bob_ws:
        bob_ws.receive_json()
        lobby_action(ws_client, lobby["uuid"], "start")

        removed = bob_ws.receive_json()
        assert removed["type"] == "lobby.removed"
        assert removed["reason"] == "not_member"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            bob_ws.receive_json()
        assert exc_info.value.code == 4403


def test_state_get_and_invalid_action_keep_the_socket_open(
    ws_client: TestClient,
    movie_factory: Callable[..., int],
) -> None:
    insert_movies(movie_factory, 1)
    alice_session = register(ws_client, "alice")
    lobby = create_lobby(ws_client)

    with websocket_for(ws_client, lobby["uuid"], alice_session) as alice_ws:
        alice_ws.receive_json()

        alice_ws.send_json({"action": "state.get"})
        state = alice_ws.receive_json()
        assert state["type"] == "lobby.state"

        alice_ws.send_json({"action": "dance"})
        error = alice_ws.receive_json()
        assert error["type"] == "lobby.error"
        assert error["code"] == "invalid_action"

        alice_ws.send_json({"action": "state.get"})
        assert alice_ws.receive_json()["type"] == "lobby.state"
