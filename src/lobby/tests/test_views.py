from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from groups.models import Group, GroupMovie
from lobby.models import LobbyCard, LobbySession
from movies.models import Movie

User = get_user_model()


def make_movie(tmdb_id=1, title="Dune"):
    return Movie.objects.create(tmdb_id=tmdb_id, title=title)


class LobbyViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pw")
        self.u2 = User.objects.create_user(username="u2", password="pw")
        self.group = Group.objects.create(name="g")
        self.group.members.add(self.u1, self.u2)
        self.client.login(username="u1", password="pw")

    def test_group_page_shows_lobby_entry(self):
        response = self.client.get(reverse("group", args=[self.group.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start movie lobby")

    def test_create_waiting_answer_start_flow(self):
        response = self.client.post(reverse("lobby:create"), {"group_uuid": str(self.group.uuid)})
        session = LobbySession.objects.get(group=self.group)
        self.assertRedirects(response, reverse("lobby:waiting", args=[session.id]))

        self.client.login(username="u2", password="pw")
        self.client.post(reverse("lobby:join", args=[session.id]))

        session.refresh_from_db()
        answers = {f"answer_{q['id']}": q["options"][0]["key"] for q in session.quiz_snapshot["questions"]}
        self.client.post(reverse("lobby:answer", args=[session.id]), answers)

        self.client.login(username="u1", password="pw")
        make_movie()
        with patch("lobby.views.recommender.refill_session", return_value=[]):
            self.client.post(reverse("lobby:start", args=[session.id]))
        session.refresh_from_db()
        self.assertEqual(session.status, LobbySession.Status.ACTIVE)

        waiting = self.client.get(reverse("lobby:waiting", args=[session.id]))
        self.assertEqual(waiting.status_code, 200)
        # Same three questions rendered for the participant.
        for q in session.quiz_snapshot["questions"]:
            self.assertContains(waiting, q["text"])

    def test_ballot_page_hides_individual_choices(self):
        from lobby import services

        m1, m2 = make_movie(1, "A"), make_movie(2, "B")
        session = services.create_session(self.group, self.u1)
        services.join_session(session, self.u2)
        services.queue_movies(session, [m1, m2])
        services.start_session(session, self.u1)

        self.client.post(reverse("lobby:ballot", args=[session.id]), {"choice": "want"})
        page = self.client.get(reverse("lobby:active", args=[session.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "1 / 2 voted")
        # Voted state hides the ballot buttons; no per-user choices rendered.
        content = page.content.decode()
        self.assertIn("You voted", content)
        self.assertNotIn('name="choice"', content)
        self.assertNotIn("u2", content)

    def test_offer_popup_and_response(self):
        from lobby import services

        m1, m2 = make_movie(1, "A"), make_movie(2, "B")
        session = services.create_session(self.group, self.u1)
        services.join_session(session, self.u2)
        services.queue_movies(session, [m1, m2])
        services.start_session(session, self.u1)
        services.submit_ballot(session, self.u1, "watched")
        services.submit_ballot(session, self.u2, "want")

        self.client.login(username="u2", password="pw")
        page = self.client.get(reverse("lobby:active", args=[session.id]))
        self.assertContains(page, "Add to group")

        from lobby.models import WatchlistOfferResponse

        resp = WatchlistOfferResponse.objects.get(participant__user=self.u2)
        self.client.post(reverse("lobby:offer_respond", args=[resp.offer_id]), {"response": "add"})
        self.assertTrue(GroupMovie.objects.filter(group=self.group, movie=m1).exists())

    def test_manual_nominate_resolves_without_group_side_effects(self):
        from lobby import services

        session = services.create_session(self.group, self.u1)
        services.join_session(session, self.u2)
        with patch("lobby.views.resolve_movie") as mock_resolve:
            movie = make_movie(99, "Manual")
            mock_resolve.return_value = movie
            self.client.post(reverse("lobby:nominate", args=[session.id]), {"tmdb_id": "99", "media_type": "movie"})
            self.assertTrue(LobbyCard.objects.filter(session=session, movie=movie).exists())
            # Nomination alone never creates a group entry.
            self.assertFalse(GroupMovie.objects.filter(group=self.group, movie=movie).exists())

    def test_non_member_cannot_open_lobby(self):
        from lobby import services

        session = services.create_session(self.group, self.u1)
        User.objects.create_user(username="out", password="pw")
        self.client.login(username="out", password="pw")
        self.assertEqual(self.client.get(reverse("lobby:waiting", args=[session.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse("lobby:active", args=[session.id])).status_code, 403)
