import math

from django.contrib.auth import get_user_model
from django.test import TestCase

from groups.models import Group, GroupMovie, Review
from lobby import recommender, services
from lobby.models import LobbyCard
from movies.models import Movie, UserMovieLibrary

User = get_user_model()
DIM = 1024


def vec(first: float, rest: float = 0.0) -> list[float]:
    v = [rest] * DIM
    v[0] = first
    return v


def unit_x() -> list[float]:
    return vec(1.0)


def unit_y() -> list[float]:
    v = [0.0] * DIM
    v[1] = 1.0
    return v


def make_movie(tmdb_id, title, **kwargs):
    return Movie.objects.create(tmdb_id=tmdb_id, title=title, **kwargs)


class PureHelperTests(TestCase):
    def test_normalize_and_centroid(self):
        self.assertEqual(recommender.normalize_vector([3.0] + [0.0] * (DIM - 1))[0], 1.0)
        c = recommender.centroid([unit_x(), unit_x()])
        self.assertAlmostEqual(c[0], 1.0)
        self.assertIsNone(recommender.centroid([]))
        with self.assertRaises(ValueError):
            recommender.centroid([[1.0, 2.0], [1.0]])

    def test_blend_prefers_vibe_only_without_history(self):
        blended = recommender.blend_profile_vector(unit_x(), [])
        self.assertAlmostEqual(blended[0], 1.0)
        self.assertIsNone(recommender.blend_profile_vector(None, []))

    def test_blend_combines_and_normalizes(self):
        blended = recommender.blend_profile_vector(unit_x(), [unit_y()])
        norm = math.sqrt(sum(v * v for v in blended))
        self.assertAlmostEqual(norm, 1.0)
        # Vibe weight dominates by default.
        self.assertGreater(blended[0], blended[1])

    def test_rank_prefers_high_mean_low_disagreement(self):
        profiles = [unit_x(), unit_x()]
        candidates = {1: unit_x(), 2: unit_y()}
        ranked = recommender.rank_candidates(candidates, profiles)
        self.assertEqual([r.movie_id for r in ranked], [1, 2])
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_rank_penalizes_disagreement(self):
        profiles = [unit_x(), unit_y()]
        mid = recommender.normalize_vector([1.0, 1.0] + [0.0] * (DIM - 2))
        candidates = {1: mid, 2: unit_x()}
        no_penalty = {r.movie_id: r for r in recommender.rank_candidates(candidates, profiles, penalty_weight=0.0)}
        penalized = {r.movie_id: r for r in recommender.rank_candidates(candidates, profiles, penalty_weight=2.0)}
        # Scores follow mean - penalty * std.
        self.assertAlmostEqual(no_penalty[2].score, no_penalty[2].mean_fit)
        self.assertAlmostEqual(penalized[2].score, penalized[2].mean_fit - 2.0 * penalized[2].disagreement, places=6)
        # High-disagreement candidate drops more under penalty than consensus one.
        drop_x = no_penalty[2].score - penalized[2].score
        drop_mid = no_penalty[1].score - penalized[1].score
        self.assertGreater(drop_x, drop_mid)
        self.assertGreater(penalized[1].score, penalized[2].score)


class RecommenderDBTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user(username="u1", password="pw")
        self.u2 = User.objects.create_user(username="u2", password="pw")
        self.group = Group.objects.create(name="g")
        self.group.members.add(self.u1, self.u2)
        self.session = services.create_session(self.group, self.u1)
        services.join_session(self.session, self.u2)
        # Give both participants valid quiz answers.
        snapshot = self.session.quiz_snapshot
        answers = {q["id"]: q["options"][0]["key"] for q in snapshot["questions"]}
        services.submit_quiz_answers(self.session, self.u1, answers)
        answers2 = {q["id"]: q["options"][1]["key"] for q in snapshot["questions"]}
        services.submit_quiz_answers(self.session, self.u2, answers2)
        self.session = services.start_session(self.session, self.u1)

    def test_history_threshold_and_watchlist_seeds(self):
        reviewed = make_movie(1, "Reviewed", embeddings=unit_x())
        low = make_movie(2, "Low", embeddings=unit_x())
        gm = GroupMovie.objects.create(group=self.group, movie=reviewed)
        GroupMovie.objects.create(group=self.group, movie=low)
        Review.objects.create(group_movie=gm, user=self.u1, score=9)
        Review.objects.create(group_movie=GroupMovie.objects.get(group=self.group, movie=low), user=self.u1, score=5)
        watch_seed = make_movie(3, "Seed", embeddings=unit_y())
        UserMovieLibrary.objects.create(user=self.u1, movie=watch_seed, watchlist_added_at="2026-01-01T00:00:00Z")
        vectors = recommender.positive_seed_vectors(self.u1)
        self.assertEqual(len(vectors), 2)
        # Other user has no seeds.
        self.assertEqual(recommender.positive_seed_vectors(self.u2), [])

    def test_retrieve_excludes_adult_group_watched_and_session_cards(self):
        good = make_movie(10, "Good", embeddings=unit_x(), popularity=5, vote_count=10)
        adult = make_movie(11, "Adult", embeddings=unit_x(), adult=True)
        listed_movie = make_movie(12, "Listed", embeddings=unit_x())
        GroupMovie.objects.create(group=self.group, movie=listed_movie)
        watched = make_movie(13, "Watched", embeddings=unit_x())
        UserMovieLibrary.objects.create(user=self.u1, movie=watched, first_watched_at="2026-01-01T00:00:00Z")
        queued = make_movie(14, "Queued", embeddings=unit_x())
        LobbyCard.objects.create(session=self.session, movie=queued, position=1)
        profiles = [recommender.ParticipantProfile(1, 1, "intent", unit_x())]
        pooled = recommender.retrieve_candidates(profiles, self.session, per_profile=10)
        self.assertIn(good.id, pooled)
        for excluded in (adult, listed_movie, watched, queued):
            self.assertNotIn(excluded.id, pooled)

    def test_recommend_falls_back_to_popularity(self):
        low = make_movie(20, "LowPop", popularity=1, vote_count=1)
        high = make_movie(21, "HighPop", popularity=99, vote_count=500)
        # No embeddings, no profiles -> popularity order.
        movies = recommender.recommend_movies(self.session, embed_fn=lambda intent: None)
        self.assertEqual([m.id for m in movies[:2]], [high.id, low.id])

    def test_recommend_ranks_by_group_fit(self):
        make_movie(30, "Far", embeddings=unit_y(), popularity=1)
        near = make_movie(31, "Near", embeddings=unit_x(), popularity=1)
        movies = recommender.recommend_movies(self.session, embed_fn=lambda intent: unit_x())
        self.assertGreaterEqual(len(movies), 2)
        self.assertEqual(movies[0].id, near.id)

    def test_refill_excludes_all_session_cards_regardless_of_status(self):
        m1 = make_movie(40, "M1", embeddings=unit_x())
        m2 = make_movie(41, "M2", embeddings=unit_x())
        services.queue_movies(self.session, [m1, m2])
        card = LobbyCard.objects.get(session=self.session, movie=m1)
        card.status = LobbyCard.Status.VETOED
        card.save(update_fields=["status"])
        pooled = recommender.retrieve_candidates(
            [recommender.ParticipantProfile(1, 1, "i", unit_x())], self.session, per_profile=10
        )
        self.assertNotIn(m1.id, pooled)
        self.assertNotIn(m2.id, pooled)

    def test_embed_failure_does_not_crash(self):
        make_movie(50, "Pop", popularity=10, vote_count=5)
        self.assertIsNone(recommender.embed_vibe_text("mood", client=object(), timeout=0.01))
        profiles = recommender.build_participant_profiles(self.session, embed_fn=lambda intent: None)
        self.assertTrue(all(p.vector is None or len(p.vector) == DIM for p in profiles))

    def test_empty_history_uses_vibe_only(self):
        profiles = recommender.build_participant_profiles(self.session, embed_fn=lambda intent: unit_x())
        for p in profiles:
            self.assertIsNotNone(p.vector)
            self.assertAlmostEqual(sum(v * v for v in p.vector), 1.0, places=5)
