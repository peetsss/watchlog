from collections.abc import Callable

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import Client, TransactionTestCase

from groups.models import Group
from lobby import engine, routing, services
from lobby.models import Lobby
from movies.models import Movie
from user.models import User
from watchlog.asgi import application as asgi_application

application = URLRouter(routing.websocket_urlpatterns)


class LobbyConsumerTests(TransactionTestCase):
    alice: User
    bob: User
    carol: User
    dave: User
    movie: Movie
    group: Group
    lobby: Lobby

    def setUp(self) -> None:
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.carol = User.objects.create_user("carol", password="pw")
        self.dave = User.objects.create_user("dave", password="pw")
        self.movies = [Movie.objects.create(title=f"Movie {i}") for i in range(1, 16)]
        self.movie = self.movies[0]
        self.group = Group.objects.create(name="Test Group")
        self.group.members.add(self.alice, self.bob, self.carol)
        lobby = services.create_lobby(self.alice, [self.bob])
        services.mark_ready(lobby.uuid, self.alice)
        self.lobby = services.mark_ready(lobby.uuid, self.bob)
        self.lobby = services.start_lobby(self.lobby.uuid, self.alice)

    def communicator(self, user: User | AnonymousUser, lobby: Lobby | None = None) -> WebsocketCommunicator:
        lobby_uuid = (lobby or self.lobby).uuid
        communicator = WebsocketCommunicator(application, f"/ws/lobby/{lobby_uuid}/")
        communicator.scope["user"] = user
        return communicator

    async def receive_type(self, communicator: WebsocketCommunicator, expected: str) -> dict[str, object]:
        for _ in range(20):
            message = await communicator.receive_json_from(timeout=5)
            if message.get("type") == expected:
                return message
        raise AssertionError(f"never received {expected}")

    async def receive_state(
        self,
        communicator: WebsocketCommunicator,
        predicate: Callable[[dict[str, object]], bool],
    ) -> dict[str, object]:
        for _ in range(20):
            message = await communicator.receive_json_from(timeout=5)
            if message.get("type") == "lobby.state" and predicate(message["lobby"]):
                return message
        raise AssertionError("never received the expected lobby state")

    async def connect_pair(self) -> tuple[WebsocketCommunicator, WebsocketCommunicator]:
        alice_comm = self.communicator(self.alice)
        bob_comm = self.communicator(self.bob)
        self.assertTrue((await alice_comm.connect())[0])
        self.assertTrue((await bob_comm.connect())[0])
        await self.receive_state(alice_comm, lambda state: True)
        await self.receive_state(bob_comm, lambda state: True)
        return alice_comm, bob_comm

    def test_unauthenticated_and_non_member_are_rejected(self) -> None:
        async def scenario() -> None:
            anonymous = self.communicator(AnonymousUser())
            self.assertFalse((await anonymous.connect())[0])
            outsider = self.communicator(self.dave)
            self.assertFalse((await outsider.connect())[0])

        async_to_sync(scenario)()

    def test_asgi_session_authentication(self) -> None:
        client = Client()
        self.assertTrue(client.login(username="alice", password="pw"))
        session_key = client.cookies[settings.SESSION_COOKIE_NAME].value
        path = f"/ws/lobby/{self.lobby.uuid}/"

        async def scenario() -> None:
            member = WebsocketCommunicator(
                asgi_application,
                path,
                headers=[
                    (b"cookie", f"{settings.SESSION_COOKIE_NAME}={session_key}".encode()),
                    (b"origin", b"http://localhost"),
                ],
            )
            self.assertTrue((await member.connect())[0])
            state = await self.receive_state(member, lambda data: True)
            self.assertEqual(state["lobby"]["viewer_id"], self.alice.pk)
            await member.disconnect()

            anonymous = WebsocketCommunicator(
                asgi_application,
                path,
                headers=[(b"origin", b"http://localhost")],
            )
            self.assertFalse((await anonymous.connect())[0])

        async_to_sync(scenario)()

    def test_connect_receives_personalized_state(self) -> None:
        async def scenario() -> None:
            alice_comm = self.communicator(self.alice)
            bob_comm = self.communicator(self.bob)
            self.assertTrue((await alice_comm.connect())[0])
            self.assertTrue((await bob_comm.connect())[0])
            alice_state = await self.receive_state(alice_comm, lambda state: True)
            bob_state = await self.receive_state(bob_comm, lambda state: True)
            self.assertTrue(alice_state["lobby"]["viewer_is_host"])
            self.assertFalse(bob_state["lobby"]["viewer_is_host"])
            self.assertEqual(alice_state["lobby"]["player_count"], 2)
            self.assertEqual(alice_state["lobby"]["status"], Lobby.Status.PLAYING)
            self.assertIsNotNone(alice_state["lobby"]["current_movie"])
            await alice_comm.disconnect()
            await bob_comm.disconnect()

        async_to_sync(scenario)()

    def test_vote_broadcast_reveal_and_next_round(self) -> None:
        async def scenario() -> None:
            alice_comm, bob_comm = await self.connect_pair()
            current = self.lobby.pool[self.lobby.pool_index]

            await alice_comm.send_json_to({"action": "vote", "movie_id": current, "choice": engine.INTERESTED})
            alice_after = await self.receive_state(
                alice_comm, lambda state: state["submitted_count"] == 1 and not state["revealed"]
            )
            bob_after = await self.receive_state(
                bob_comm, lambda state: state["submitted_count"] == 1 and not state["revealed"]
            )
            self.assertEqual(alice_after["lobby"]["viewer_vote"], engine.INTERESTED)
            self.assertFalse(alice_after["lobby"]["revealed"])
            self.assertIsNone(bob_after["lobby"]["viewer_vote"])
            self.assertEqual(bob_after["lobby"]["submitted_count"], 1)
            self.assertEqual(bob_after["lobby"]["ballot"], [])

            await bob_comm.send_json_to({"action": "vote", "movie_id": current, "choice": engine.WATCHED})
            alice_revealed = await self.receive_state(alice_comm, lambda state: state["revealed"] is True)
            bob_revealed = await self.receive_state(bob_comm, lambda state: state["revealed"] is True)
            self.assertTrue(alice_revealed["lobby"]["revealed"])
            self.assertEqual(alice_revealed["lobby"]["vote_tally"]["interested"], 1)
            self.assertEqual(bob_revealed["lobby"]["vote_tally"]["watched"], 1)
            self.assertEqual(len(bob_revealed["lobby"]["ballot"]), 2)
            self.assertEqual(bob_revealed["lobby"]["finalists"], [])

            await bob_comm.send_json_to({"action": "next_round"})
            advanced = await self.receive_state(bob_comm, lambda state: state["pool_index"] == 1)
            self.assertEqual(advanced["lobby"]["pool_index"], 1)
            self.assertFalse(advanced["lobby"]["revealed"])
            await alice_comm.disconnect()
            await bob_comm.disconnect()

        async_to_sync(scenario)()

    def test_pick_privacy_and_finalize(self) -> None:
        final = self.play_to_final()

        async def scenario() -> None:
            alice_comm, bob_comm = await self.connect_pair()
            winner = final.finalists[0]

            await alice_comm.send_json_to({"action": "pick", "movie_id": winner})
            alice_after = await self.receive_state(
                alice_comm, lambda state: state["submitted_count"] == 1 and not state["revealed"]
            )
            bob_after = await self.receive_state(
                bob_comm, lambda state: state["submitted_count"] == 1 and not state["revealed"]
            )
            self.assertEqual(alice_after["lobby"]["viewer_pick"], winner)
            self.assertIsNone(bob_after["lobby"]["viewer_pick"])
            self.assertIsNone(bob_after["lobby"]["finalists"][0]["pick_count"])

            await bob_comm.send_json_to({"action": "pick", "movie_id": winner})
            alice_revealed = await self.receive_state(alice_comm, lambda state: state["picks_revealed"] is True)
            bob_revealed = await self.receive_state(bob_comm, lambda state: state["picks_revealed"] is True)
            self.assertTrue(alice_revealed["lobby"]["picks_revealed"])
            self.assertEqual(bob_revealed["lobby"]["finalists"][0]["pick_count"], 2)
            self.assertIsNone(bob_revealed["lobby"]["winner"])

            await bob_comm.send_json_to({"action": "finalize"})
            finished = await self.receive_state(bob_comm, lambda state: state["status"] == Lobby.Status.FINISHED)
            self.assertEqual(finished["lobby"]["status"], Lobby.Status.FINISHED)
            self.assertEqual(finished["lobby"]["winner"]["id"], winner)
            await alice_comm.disconnect()
            await bob_comm.disconnect()

        async_to_sync(scenario)()

    def test_start_removes_unready_members_and_closes_them(self) -> None:
        lobby = services.create_lobby(self.alice, [self.bob, self.carol])

        async def scenario() -> None:
            alice_comm = self.communicator(self.alice, lobby)
            bob_comm = self.communicator(self.bob, lobby)
            carol_comm = self.communicator(self.carol, lobby)
            self.assertTrue((await alice_comm.connect())[0])
            self.assertTrue((await bob_comm.connect())[0])
            self.assertTrue((await carol_comm.connect())[0])
            await self.receive_type(alice_comm, "lobby.state")
            await self.receive_type(bob_comm, "lobby.state")
            await self.receive_type(carol_comm, "lobby.state")

            await bob_comm.send_json_to({"action": "ready"})
            await self.receive_state(bob_comm, lambda state: state["viewer_ready"] is True)
            await alice_comm.send_json_to({"action": "start"})
            started = await self.receive_state(bob_comm, lambda state: state["status"] == Lobby.Status.PLAYING)
            self.assertEqual(started["lobby"]["status"], Lobby.Status.PLAYING)
            removed = await self.receive_type(carol_comm, "lobby.removed")
            self.assertEqual(removed["reason"], "not_member")
            await alice_comm.disconnect()
            await bob_comm.disconnect()

        async_to_sync(scenario)()

    def test_leave_closes_guest_and_updates_host(self) -> None:
        async def scenario() -> None:
            alice_comm, bob_comm = await self.connect_pair()
            await bob_comm.send_json_to({"action": "leave"})
            left = await self.receive_type(bob_comm, "lobby.left")
            self.assertEqual(left["type"], "lobby.left")
            host_state = await self.receive_state(alice_comm, lambda state: state["player_count"] == 1)
            self.assertEqual(host_state["lobby"]["player_count"], 1)
            await alice_comm.disconnect()

        async_to_sync(scenario)()

    def test_state_get_and_unknown_action(self) -> None:
        async def scenario() -> None:
            alice_comm = self.communicator(self.alice)
            self.assertTrue((await alice_comm.connect())[0])
            await self.receive_state(alice_comm, lambda state: True)

            await alice_comm.send_json_to({"action": "state.get"})
            state = await self.receive_state(alice_comm, lambda state: True)
            self.assertEqual(state["lobby"]["uuid"], str(self.lobby.uuid))

            await alice_comm.send_json_to({"action": "dance"})
            error = await self.receive_type(alice_comm, "lobby.error")
            self.assertEqual(error["code"], "invalid_action")
            await alice_comm.disconnect()

        async_to_sync(scenario)()

    def test_restart_returns_new_lobby_and_closes(self) -> None:
        services.end_lobby(self.lobby.uuid, self.alice)

        async def scenario() -> None:
            alice_comm = self.communicator(self.alice)
            self.assertTrue((await alice_comm.connect())[0])
            await self.receive_state(alice_comm, lambda state: True)
            await alice_comm.send_json_to({"action": "restart"})
            restarted = await self.receive_type(alice_comm, "lobby.restarted")
            self.assertNotEqual(restarted["new_lobby_uuid"], str(self.lobby.uuid))
            self.assertEqual(restarted["lobby"]["status"], Lobby.Status.READY)
            await alice_comm.disconnect()

        async_to_sync(scenario)()
        self.assertEqual(Lobby.objects.filter(status=Lobby.Status.READY).count(), 1)

    def play_to_final(self) -> Lobby:
        lobby = self.lobby
        while lobby.status == Lobby.Status.PLAYING:
            if lobby.revealed:
                lobby = services.next_round(lobby.uuid, self.alice)
            else:
                current = lobby.pool[lobby.pool_index]
                for user in (self.alice, self.bob):
                    lobby = services.vote(lobby.uuid, user, current, engine.INTERESTED)
        self.assertEqual(lobby.status, Lobby.Status.FINAL_ROUND)
        return lobby
