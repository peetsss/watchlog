import json
from uuid import uuid4

from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from groups.models import Group
from lobby import engine, services
from lobby.models import Lobby
from movies.models import Movie
from user.models import User


class LobbyApiTestCase(TestCase):
    alice: User
    bob: User
    carol: User
    dave: User
    movies: list[Movie]
    group: Group

    @classmethod
    def setUpTestData(cls) -> None:
        cls.alice = User.objects.create_user("alice", password="pw")
        cls.bob = User.objects.create_user("bob", password="pw")
        cls.carol = User.objects.create_user("carol", password="pw")
        cls.dave = User.objects.create_user("dave", password="pw")
        cls.movies = [Movie.objects.create(title=f"Movie {i}") for i in range(1, 16)]
        cls.group = Group.objects.create(name="Test Group")
        cls.group.members.add(cls.alice, cls.bob, cls.carol)

    def setUp(self) -> None:
        self.client = Client()
        self.login(self.alice)

    def login(self, user: User) -> None:
        self.client.force_login(user)

    def post_json(self, url: str, payload: dict[str, object] | None = None) -> HttpResponse:
        return self.client.post(url, data=json.dumps(payload or {}), content_type="application/json")

    def create_open(self) -> dict[str, object]:
        response = self.post_json(reverse("lobby:create"))
        self.assertEqual(response.status_code, 201)
        return response.json()["lobby"]

    def state_url(self, lobby_uuid: str) -> str:
        return reverse("lobby:state", kwargs={"lobby_uuid": lobby_uuid})

    def action_url(self, lobby_uuid: str, action: str) -> str:
        return reverse("lobby:action", kwargs={"lobby_uuid": lobby_uuid, "action": action})

    def get_state(self, lobby_uuid: str) -> dict[str, object]:
        response = self.client.get(self.state_url(lobby_uuid))
        self.assertEqual(response.status_code, 200)
        return response.json()["lobby"]

    def create_final_lobby(self) -> Lobby:
        lobby = services.create_lobby(self.alice, [self.bob])
        for user in (self.alice, self.bob):
            lobby = services.mark_ready(lobby.uuid, user)
        lobby = services.start_lobby(lobby.uuid, self.alice)
        while lobby.status == Lobby.Status.PLAYING:
            if lobby.revealed:
                lobby = services.next_round(lobby.uuid, self.alice)
            else:
                current = lobby.pool[lobby.pool_index]
                for user in (self.alice, self.bob):
                    lobby = services.vote(lobby.uuid, user, current, engine.INTERESTED)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        return lobby


class CreateApiTest(LobbyApiTestCase):
    def test_csrf_endpoint_returns_a_token_and_cookie(self) -> None:
        response = self.client.get(reverse("lobby:csrf"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrfToken", response.json())
        self.assertIn("csrftoken", response.cookies)

    def test_create_open_lobby_returns_state(self) -> None:
        lobby = self.create_open()
        self.assertEqual(lobby["type"], Lobby.Type.OPEN)
        self.assertEqual(lobby["status"], Lobby.Status.READY)
        self.assertTrue(lobby["viewer_is_host"])
        self.assertEqual(lobby["player_count"], 1)
        self.assertEqual(lobby["version"], 0)

    def test_create_group_lobby(self) -> None:
        response = self.post_json(reverse("lobby:create"), {"group_uuid": str(self.group.uuid)})
        self.assertEqual(response.status_code, 201)
        lobby = response.json()["lobby"]
        self.assertEqual(lobby["type"], Lobby.Type.GROUP)
        self.assertEqual(lobby["group_uuid"], str(self.group.uuid))
        self.assertEqual(lobby["player_count"], 3)

    def test_create_group_lobby_requires_group_membership(self) -> None:
        self.login(self.dave)
        response = self.post_json(reverse("lobby:create"), {"group_uuid": str(self.group.uuid)})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "not_a_member")

    def test_create_rejects_unknown_and_malformed_groups(self) -> None:
        response = self.post_json(reverse("lobby:create"), {"group_uuid": str(uuid4())})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

        response = self.post_json(reverse("lobby:create"), {"group_uuid": "not-a-uuid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_action")

    def test_authentication_is_required(self) -> None:
        self.client.logout()
        response = self.client.get(reverse("lobby:active"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "unauthorized")


class JoinApiTest(LobbyApiTestCase):
    def test_open_lobby_preview_and_join(self) -> None:
        lobby = self.create_open()
        lobby_uuid = lobby["uuid"]
        self.login(self.bob)
        preview = self.client.get(reverse("lobby:preview", kwargs={"lobby_uuid": lobby_uuid}))
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["preview"]["can_join"])

        response = self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby_uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lobby"]["player_count"], 2)
        self.assertEqual(response.json()["lobby"]["status"], Lobby.Status.READY)

        again = self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby_uuid}))
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["lobby"]["player_count"], 2)

    def test_group_lobby_preview_and_join_are_private(self) -> None:
        lobby = services.create_lobby(self.alice, group=self.group)
        self.login(self.dave)
        preview = self.client.get(reverse("lobby:preview", kwargs={"lobby_uuid": lobby.uuid}))
        self.assertEqual(preview.status_code, 403)
        join = self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby.uuid}))
        self.assertEqual(join.status_code, 409)
        self.assertEqual(join.json()["error"]["code"], "not_joinable")

    def test_join_after_start_is_rejected(self) -> None:
        lobby = services.create_lobby(self.alice)
        services.mark_ready(lobby.uuid, self.alice)
        services.start_lobby(lobby.uuid, self.alice)
        self.login(self.bob)
        response = self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby.uuid}))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "not_joinable")


class ActionApiTest(LobbyApiTestCase):
    def test_ready_unready_and_host_start(self) -> None:
        lobby = self.create_open()
        lobby_uuid = lobby["uuid"]
        response = self.post_json(self.action_url(lobby_uuid, "ready"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["lobby"]["viewer_ready"])

        response = self.post_json(self.action_url(lobby_uuid, "unready"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["lobby"]["viewer_ready"])

        self.login(self.bob)
        response = self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby_uuid}))
        self.assertEqual(response.status_code, 200)
        forbidden = self.post_json(self.action_url(lobby_uuid, "start"))
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["error"]["code"], "not_host")

        self.login(self.alice)
        started = self.post_json(self.action_url(lobby_uuid, "start"))
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["lobby"]["status"], Lobby.Status.PLAYING)

    def test_vote_reveal_and_next_round(self) -> None:
        lobby = self.create_open()
        lobby_uuid = lobby["uuid"]
        started = self.post_json(self.action_url(lobby_uuid, "start"))
        self.assertEqual(started.json()["lobby"]["status"], Lobby.Status.PLAYING)
        current = started.json()["lobby"]["current_movie"]["id"]

        invalid = self.post_json(self.action_url(lobby_uuid, "vote"), {"movie_id": current, "choice": "maybe"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "invalid_choice")

        voted = self.post_json(
            self.action_url(lobby_uuid, "vote"),
            {"movie_id": current, "choice": engine.INTERESTED},
        )
        self.assertEqual(voted.status_code, 200)
        voted_lobby = voted.json()["lobby"]
        self.assertTrue(voted_lobby["revealed"])
        self.assertEqual(voted_lobby["vote_tally"]["interested"], 1)
        self.assertEqual(voted_lobby["ballot"][0]["choice"], engine.INTERESTED)

        advanced = self.post_json(self.action_url(lobby_uuid, "next-round"))
        self.assertEqual(advanced.status_code, 200)
        self.assertFalse(advanced.json()["lobby"]["revealed"])
        self.assertEqual(advanced.json()["lobby"]["pool_index"], 1)

    def test_vote_after_reveal_is_rejected(self) -> None:
        lobby = self.create_open()
        started = self.post_json(self.action_url(lobby["uuid"], "start")).json()["lobby"]
        current = started["current_movie"]["id"]
        self.post_json(self.action_url(lobby["uuid"], "vote"), {"movie_id": current, "choice": engine.INTERESTED})
        response = self.post_json(self.action_url(lobby["uuid"], "vote"), {"movie_id": current, "choice": "watched"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "invalid_state")

    def test_pick_privacy_and_finalize(self) -> None:
        final = self.create_final_lobby()
        winner = final.finalists[0]
        response = self.post_json(self.action_url(str(final.uuid), "pick"), {"movie_id": winner})
        self.assertEqual(response.status_code, 200)

        self.login(self.bob)
        bob_state = self.get_state(str(final.uuid))
        self.assertFalse(bob_state["picks_revealed"])
        self.assertIsNone(bob_state["finalists"][0]["pick_count"])
        self.assertEqual(bob_state["submitted_count"], 1)

        response = self.post_json(self.action_url(str(final.uuid), "pick"), {"movie_id": winner})
        self.assertEqual(response.status_code, 200)
        bob_state = response.json()["lobby"]
        self.assertTrue(bob_state["picks_revealed"])
        self.assertEqual(bob_state["finalists"][0]["pick_count"], 2)
        self.assertIsNone(bob_state["winner"])

        response = self.post_json(self.action_url(str(final.uuid), "finalize"))
        self.assertEqual(response.status_code, 200)
        finished = response.json()["lobby"]
        self.assertEqual(finished["status"], Lobby.Status.FINISHED)
        self.assertEqual(finished["winner"]["id"], winner)

    def test_host_advance_and_guest_rejection(self) -> None:
        lobby = self.create_open()
        self.login(self.bob)
        self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby["uuid"]}))
        self.login(self.alice)
        self.post_json(self.action_url(lobby["uuid"], "start"))
        self.login(self.bob)
        guest = self.post_json(self.action_url(lobby["uuid"], "advance"))
        self.assertEqual(guest.status_code, 403)

    def test_leave_and_host_leave(self) -> None:
        lobby = self.create_open()
        lobby_uuid = lobby["uuid"]
        self.login(self.bob)
        self.post_json(reverse("lobby:join", kwargs={"lobby_uuid": lobby_uuid}))
        self.post_json(self.action_url(lobby_uuid, "ready"))
        self.login(self.alice)
        self.post_json(self.action_url(lobby_uuid, "start"))
        self.login(self.bob)
        response = self.post_json(self.action_url(lobby_uuid, "leave"))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(self.state_url(lobby_uuid)).status_code, 403)

        self.login(self.alice)
        host_leave = self.post_json(self.action_url(lobby_uuid, "leave"))
        self.assertEqual(host_leave.status_code, 403)

    def test_end_and_restart(self) -> None:
        lobby = self.create_open()
        ended = self.post_json(self.action_url(lobby["uuid"], "end"))
        self.assertEqual(ended.status_code, 200)
        self.assertEqual(ended.json()["lobby"]["status"], Lobby.Status.FINISHED)

        restarted = self.post_json(self.action_url(lobby["uuid"], "restart"))
        self.assertEqual(restarted.status_code, 201)
        payload = restarted.json()
        self.assertNotEqual(payload["lobby"]["uuid"], lobby["uuid"])
        self.assertEqual(payload["previous_uuid"], lobby["uuid"])
        self.assertEqual(payload["lobby"]["status"], Lobby.Status.READY)

    def test_unknown_action_and_malformed_json(self) -> None:
        lobby = self.create_open()
        unknown = self.post_json(self.action_url(lobby["uuid"], "dance"))
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.json()["error"]["code"], "invalid_action")

        response = self.client.post(
            self.action_url(lobby["uuid"], "ready"),
            data="{not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_action")


class StateApiTest(LobbyApiTestCase):
    def test_state_etag_and_not_modified(self) -> None:
        lobby = self.create_open()
        response = self.client.get(self.state_url(lobby["uuid"]))
        self.assertEqual(response.status_code, 200)
        etag = response.headers["ETag"]
        self.assertEqual(etag, '"v0"')

        unchanged = self.client.get(self.state_url(lobby["uuid"]), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(unchanged.status_code, 304)

        self.post_json(self.action_url(lobby["uuid"], "ready"))
        changed = self.client.get(self.state_url(lobby["uuid"]), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(changed.status_code, 200)

    def test_state_requires_membership_and_unknown_lobby_is_404(self) -> None:
        lobby = self.create_open()
        self.login(self.dave)
        forbidden = self.client.get(self.state_url(lobby["uuid"]))
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["error"]["code"], "not_a_member")

        self.login(self.alice)
        missing = self.client.get(self.state_url(str(uuid4())))
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "not_found")

    def test_active_endpoint(self) -> None:
        lobby = self.create_open()
        response = self.client.get(reverse("lobby:active"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active"]["uuid"], lobby["uuid"])

        self.post_json(self.action_url(lobby["uuid"], "end"))
        response = self.client.get(reverse("lobby:active"))
        self.assertIsNone(response.json()["active"])

    def test_csrf_is_enforced_on_mutating_requests(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        response = client.post(
            reverse("lobby:create"),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
