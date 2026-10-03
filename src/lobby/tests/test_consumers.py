from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from groups.models import Group
from lobby import routing, services
from lobby.models import LobbyCard
from movies.models import Movie

User = get_user_model()

application = URLRouter(routing.websocket_urlpatterns)


def make_movie(tmdb_id, title):
    return Movie.objects.create(tmdb_id=tmdb_id, title=title)


class LobbyConsumerTests(TransactionTestCase):
    def setUp(self):
        self.u1 = User.objects.create_user(username="c1", password="pw")
        self.u2 = User.objects.create_user(username="c2", password="pw")
        self.outsider = User.objects.create_user(username="out", password="pw")
        self.group = Group.objects.create(name="g")
        self.group.members.add(self.u1, self.u2)
        self.movie_a = make_movie(1, "Dune")
        self.movie_b = make_movie(2, "Arrival")
        session = services.create_session(self.group, self.u1)
        services.join_session(session, self.u2)
        services.queue_movies(session, [self.movie_a, self.movie_b])
        self.session = services.start_session(session, self.u1)
        self.url = f"/ws/lobby/{self.session.id}/"

    def tearDown(self):
        # Explicit disconnects happen inside each test; best-effort cleanup only.
        pass

    def _communicator(self, user):
        comm = WebsocketCommunicator(application, self.url)
        comm.scope["user"] = user
        return comm

    async def _receive_of_type(self, comm, expected_type, timeout=5):
        """Skip group broadcast events until the direct reply arrives."""
        for _ in range(10):
            msg = await comm.receive_json_from(timeout=timeout)
            if msg.get("type") == expected_type:
                return msg
            # Otherwise it is a post-commit broadcast (lobby.ballot, ...); keep draining.
        raise AssertionError(f"never received {expected_type}")

    async def test_unauthenticated_rejected(self):
        comm = self._communicator(AnonymousUser())
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()

    async def test_non_member_rejected(self):
        comm = self._communicator(self.outsider)
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()

    async def test_member_but_not_participant_rejected(self):
        await database_sync_to_async(self.group.members.add)(self.outsider)
        comm = self._communicator(self.outsider)
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()

    async def test_participant_connect_receives_private_state(self):
        comm = self._communicator(self.u1)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        initial = await comm.receive_json_from()
        self.assertEqual(initial["type"], "lobby.state")
        self.assertEqual(initial["participant_count"], 2)
        self.assertEqual(initial["submitted_count"], 0)
        self.assertIsNone(initial["own_choice"])
        self.assertIsNotNone(initial["current_card"])
        self.assertNotIn("choices", initial)
        await comm.disconnect()

    async def test_ballot_flow_hides_choices_until_complete(self):
        c1 = self._communicator(self.u1)
        c2 = self._communicator(self.u2)
        self.assertTrue((await c1.connect())[0])
        self.assertTrue((await c2.connect())[0])
        await c1.receive_json_from()
        await c2.receive_json_from()

        await c1.send_json_to({"action": "ballot.submit", "choice": "want"})
        r1 = await self._receive_of_type(c1, "lobby.ballot_result")
        self.assertEqual(r1["outcome"], "pending")
        self.assertEqual(r1["submitted_count"], 1)
        self.assertNotIn("choices", r1)

        # Reconnecting participant sees count but not the other's choice.
        await c2.send_json_to({"action": "state.get"})
        state = await self._receive_of_type(c2, "lobby.state")
        self.assertEqual(state["submitted_count"], 1)
        self.assertIsNone(state["own_choice"])

        await c2.send_json_to({"action": "ballot.submit", "choice": "not_interested"})
        r2 = await self._receive_of_type(c2, "lobby.ballot_result")
        self.assertEqual(r2["outcome"], "vetoed")
        card = await LobbyCard.objects.aget(session=self.session, movie=self.movie_a)
        self.assertEqual(card.status, LobbyCard.Status.VETOED)
        await c1.disconnect()
        await c2.disconnect()

    async def test_duplicate_ballot_and_errors_are_safe(self):
        comm = self._communicator(self.u1)
        self.assertTrue((await comm.connect())[0])
        await comm.receive_json_from()
        await comm.send_json_to({"action": "ballot.submit", "choice": "want"})
        first = await self._receive_of_type(comm, "lobby.ballot_result")
        self.assertEqual(first["outcome"], "pending")
        await comm.send_json_to({"action": "ballot.submit", "choice": "want"})
        retry = await self._receive_of_type(comm, "lobby.ballot_result")
        self.assertEqual(retry["outcome"], "pending")

        await comm.send_json_to({"action": "ballot.submit", "choice": "bogus"})
        err = await self._receive_of_type(comm, "lobby.error")
        self.assertEqual(err["type"], "lobby.error")

        await comm.send_json_to({"action": "nope"})
        err2 = await self._receive_of_type(comm, "lobby.error")
        self.assertEqual(err2["type"], "lobby.error")
        await comm.disconnect()

    async def test_offer_respond_and_reconnect(self):
        c1 = self._communicator(self.u1)
        c2 = self._communicator(self.u2)
        self.assertTrue((await c1.connect())[0])
        self.assertTrue((await c2.connect())[0])
        await c1.receive_json_from()
        await c2.receive_json_from()
        await c1.send_json_to({"action": "ballot.submit", "choice": "watched"})
        await self._receive_of_type(c1, "lobby.ballot_result")
        await c2.send_json_to({"action": "ballot.submit", "choice": "want"})
        await self._receive_of_type(c2, "lobby.ballot_result")

        # Reconnect sees pending offer.
        c2b = self._communicator(self.u2)
        self.assertTrue((await c2b.connect())[0])
        state = await c2b.receive_json_from()
        self.assertEqual(len(state["pending_offers"]), 1)
        offer_id = state["pending_offers"][0]["offer_id"]

        # Owner responds; another user's offer id is rejected.
        await c2b.send_json_to({"action": "offer.respond", "offer_id": offer_id, "response": "add"})
        done = await self._receive_of_type(c2b, "lobby.offer_result")
        self.assertEqual(done["response"], "added")
        await c1.disconnect()
        await c2.disconnect()
        await c2b.disconnect()

    async def test_cannot_answer_for_someone_else(self):
        # Consumer derives identity from scope; no target-user field exists.
        comm = self._communicator(self.u1)
        self.assertTrue((await comm.connect())[0])
        await comm.receive_json_from()
        await comm.send_json_to({"action": "offer.respond", "offer_id": 999999, "response": "add"})
        err = await comm.receive_json_from()
        self.assertEqual(err["type"], "lobby.error")
        await comm.disconnect()


class AsgiRoutingTests(TransactionTestCase):
    def test_asgi_uses_settings_dispatcher_and_guards(self):
        import inspect

        import watchlog.asgi as asgi_module

        source = inspect.getsource(asgi_module)
        self.assertIn("watchlog.settings", source)
        self.assertNotIn("settings.dev", source)
        self.assertIn("AllowedHostsOriginValidator", source)
        self.assertIn("AuthMiddlewareStack", source)
        self.assertIn("URLRouter", source)
