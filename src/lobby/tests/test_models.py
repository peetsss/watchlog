from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from groups.models import Group
from lobby.models import (
    LobbyBallot,
    LobbyCard,
    LobbyParticipant,
    LobbySession,
    WatchlistOffer,
    WatchlistOfferResponse,
)
from lobby.quiz import select_quiz_snapshot
from movies.models import Movie

User = get_user_model()


def make_setup():
    user = User.objects.create_user(username="host", password="pw")
    other = User.objects.create_user(username="member", password="pw")
    group = Group.objects.create(name="g")
    group.members.add(user, other)
    movie = Movie.objects.create(tmdb_id=1, title="Dune")
    movie2 = Movie.objects.create(tmdb_id=2, title="Arrival")
    return user, other, group, movie, movie2


def make_session(group, host):
    return LobbySession.objects.create(group=group, host=host, quiz_snapshot=select_quiz_snapshot(seed=1))


class LobbySessionConstraintTests(TestCase):
    def test_only_one_open_session_per_group(self):
        user, _, group, _, _ = make_setup()
        make_session(group, user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_session(group, user)

    def test_new_session_allowed_after_close(self):
        user, _, group, _, _ = make_setup()
        session = make_session(group, user)
        session.status = LobbySession.Status.MATCHED
        session.save(update_fields=["status"])
        make_session(group, user)  # must not raise

    def test_uuid_is_public_identifier(self):
        user, _, group, _, _ = make_setup()
        session = make_session(group, user)
        self.assertIsNotNone(session.id)
        fetched = LobbySession.objects.get(pk=session.id)
        self.assertEqual(fetched.group, group)


class ParticipantConstraintTests(TestCase):
    def test_unique_session_user(self):
        user, other, group, _, _ = make_setup()
        session = make_session(group, user)
        LobbyParticipant.objects.create(session=session, user=user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyParticipant.objects.create(session=session, user=user)
        # Different user is fine.
        LobbyParticipant.objects.create(session=session, user=other)

    def test_quiz_answers_default_empty_and_session_scoped(self):
        user, _, group, _, _ = make_setup()
        session = make_session(group, user)
        p = LobbyParticipant.objects.create(session=session, user=user, quiz_answers={"energy": "light"})
        self.assertEqual(p.quiz_answers, {"energy": "light"})
        # No global profile field on user.
        self.assertFalse(hasattr(user, "vibe_embedding"))


class CardConstraintTests(TestCase):
    def test_unique_session_movie(self):
        user, _, group, movie, _ = make_setup()
        session = make_session(group, user)
        LobbyCard.objects.create(session=session, movie=movie, position=0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyCard.objects.create(session=session, movie=movie, position=1)

    def test_only_one_current_card_per_session(self):
        user, _, group, movie, movie2 = make_setup()
        session = make_session(group, user)
        LobbyCard.objects.create(session=session, movie=movie, position=0, status=LobbyCard.Status.CURRENT)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyCard.objects.create(session=session, movie=movie2, position=1, status=LobbyCard.Status.CURRENT)

    def test_queued_cards_can_coexist(self):
        user, _, group, movie, movie2 = make_setup()
        session = make_session(group, user)
        LobbyCard.objects.create(session=session, movie=movie, position=0)
        LobbyCard.objects.create(session=session, movie=movie2, position=1)
        self.assertEqual(session.cards.count(), 2)


class BallotOfferConstraintTests(TestCase):
    def setUp(self):
        self.user, self.other, self.group, self.movie, _ = make_setup()
        self.session = make_session(self.group, self.user)
        self.pa = LobbyParticipant.objects.create(session=self.session, user=self.user)
        self.pb = LobbyParticipant.objects.create(session=self.session, user=self.other)
        self.card = LobbyCard.objects.create(
            session=self.session, movie=self.movie, position=0, status=LobbyCard.Status.CURRENT
        )

    def test_unique_ballot_per_card_participant(self):
        LobbyBallot.objects.create(card=self.card, participant=self.pa, choice=LobbyBallot.Choice.WANT)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LobbyBallot.objects.create(card=self.card, participant=self.pa, choice=LobbyBallot.Choice.WANT)

    def test_one_offer_per_card(self):
        WatchlistOffer.objects.create(card=self.card)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WatchlistOffer.objects.create(card=self.card)

    def test_one_response_per_offer_participant(self):
        offer = WatchlistOffer.objects.create(card=self.card)
        WatchlistOfferResponse.objects.create(offer=offer, participant=self.pb)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WatchlistOfferResponse.objects.create(offer=offer, participant=self.pb)


class ModelStrTests(TestCase):
    def test_str_never_queries_db(self):
        user, _, group, movie, _ = make_setup()
        session = make_session(group, user)
        participant = LobbyParticipant.objects.create(session=session, user=user)
        card = LobbyCard.objects.create(session=session, movie=movie, position=0)
        ballot = LobbyBallot.objects.create(card=card, participant=participant, choice=LobbyBallot.Choice.WANT)
        offer = WatchlistOffer.objects.create(card=card)
        response = WatchlistOfferResponse.objects.create(offer=offer, participant=participant)
        with self.assertNumQueries(0):
            for obj in (session, participant, card, ballot, offer, response):
                str(obj)
