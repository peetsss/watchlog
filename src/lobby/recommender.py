"""Per-participant taste profiles, pgvector candidates, group-fit ranking.

Network boundary: vibe embedding happens here, never inside a DB row lock.
All ranking math lives in pure helpers so it can be tuned/evaluated
independently. Deterministic popularity fallback when embeddings or the
recommender are unavailable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pgvector.django import CosineDistance

from groups.models import GroupMovie, Review
from movies.models import Movie, UserMovieLibrary
from movies.utils.embeddings import (
    EMBED_DIMENSIONS,
    format_query_for_embedding,
    request_embeddings,
)

from . import rules
from .models import LobbyParticipant, LobbySession
from .quiz import build_intent_text


@dataclass(frozen=True, slots=True)
class ParticipantProfile:
    participant_id: int
    user_id: int
    intent_text: str
    vector: list[float] | None


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    movie_id: int
    score: float
    mean_fit: float
    disagreement: float


def normalize_vector(vector: list[float]) -> list[float]:
    """L2-normalize; zero vectors map to themselves."""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return list(vector)
    return [v / norm for v in vector]


def centroid(vectors: list[list[float]]) -> list[float] | None:
    """Mean vector; None when empty. All vectors must share dimensionality."""
    if not vectors:
        return None
    dim = len(vectors[0])
    if any(len(v) != dim for v in vectors):
        raise ValueError("all vectors must share dimensionality")
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def blend_profile_vector(
    vibe_vector: list[float] | None,
    history_vectors: list[list[float]],
    *,
    vibe_weight: float = rules.PROFILE_VIBE_WEIGHT,
    history_weight: float = rules.PROFILE_HISTORY_WEIGHT,
) -> list[float] | None:
    """Blend vibe + history centroid; normalize. Vibe-only if no history.

    Returns None when neither source yields a usable vector (caller falls
    back to popularity).
    """
    history_centroid = centroid(history_vectors)
    if vibe_vector is None and history_centroid is None:
        return None
    if vibe_vector is None:
        assert history_centroid is not None
        return normalize_vector(history_centroid)
    if history_centroid is None:
        return normalize_vector(vibe_vector)
    if len(vibe_vector) != len(history_centroid):
        raise ValueError("vibe and history vectors must share dimensionality")
    blended = [vibe_weight * v + history_weight * h for v, h in zip(vibe_vector, history_centroid, strict=True)]
    return normalize_vector(blended)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0 when either vector is zero."""
    norm_a = math.sqrt(sum(v * v for v in a))
    norm_b = math.sqrt(sum(v * v for v in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def rank_candidates(
    candidate_vectors: dict[int, list[float]],
    profiles: list[list[float]],
    *,
    penalty_weight: float = rules.DISAGREEMENT_PENALTY_WEIGHT,
) -> list[RankedCandidate]:
    """Rank by mean fit minus penalty * std (population). Pure helper.

    Higher score first; ties broken by movie id for determinism.
    """
    ranked: list[RankedCandidate] = []
    for movie_id, vector in candidate_vectors.items():
        fits = [cosine_similarity(vector, p) for p in profiles]
        if not fits:
            continue
        mean = sum(fits) / len(fits)
        variance = sum((f - mean) ** 2 for f in fits) / len(fits)
        std = math.sqrt(variance)
        ranked.append(
            RankedCandidate(movie_id=movie_id, score=mean - penalty_weight * std, mean_fit=mean, disagreement=std)
        )
    ranked.sort(key=lambda r: (-r.score, r.movie_id))
    return ranked


def positive_seed_vectors(user) -> list[list[float]]:
    """High-scored review movies + personal watchlist seeds with embeddings."""
    review_movie_ids = Review.objects.filter(
        user=user, score__gte=rules.HISTORY_SCORE_THRESHOLD, group_movie__movie__embeddings__isnull=False
    ).values_list("group_movie__movie_id", flat=True)
    watchlist_movie_ids = UserMovieLibrary.objects.filter(
        user=user,
        watchlist_added_at__isnull=False,
        movie__embeddings__isnull=False,
    ).values_list("movie_id", flat=True)
    wanted = set(review_movie_ids) | set(watchlist_movie_ids)
    if not wanted:
        return []
    vectors: list[list[float]] = []
    for embedding in Movie.objects.filter(id__in=wanted, embeddings__isnull=False).values_list("embeddings", flat=True):
        vectors.append(list(embedding))
    return vectors


def embed_vibe_text(
    intent_text: str,
    client,
    *,
    model: str | None = None,
    ollama_url: str | None = None,
    dimensions: int = EMBED_DIMENSIONS,
    timeout: float = 30.0,
) -> list[float] | None:
    """Embed one intent string as a query; None on any failure.

    Bounded timeout; pitch/recommendation must never crash the lobby when
    Ollama is unavailable. Query-only with a dedicated VIBE_TASK.
    """
    from movies.utils import embeddings as emb

    kwargs: dict = {"timeout": timeout, "dimensions": dimensions}
    if model is not None:
        kwargs["model"] = model
    if ollama_url is not None:
        kwargs["ollama_url"] = ollama_url
    try:
        wrapped = format_query_for_embedding(intent_text, task=rules.VIBE_TASK)
        vectors = request_embeddings(client, [wrapped], **kwargs)
    except Exception:
        return None
    if len(vectors) != 1:
        return None
    if len(vectors[0]) != dimensions:
        return None
    _ = emb.EMBED_MODEL  # keep embeddings module as the single source of model defaults
    return vectors[0]


def build_participant_profiles(
    session: LobbySession,
    *,
    embed_client=None,
    embed_fn=None,
) -> list[ParticipantProfile]:
    """Compose one profile per frozen participant.

    `embed_fn(intent_text) -> vector | None` overrides network access in tests.
    When no embed client/fn is given, vibe is skipped and history-only profiles
    are built (popularity fallback downstream if those are also empty).
    """
    participants = list(session.participants.filter(state=LobbyParticipant.State.ACTIVE).select_related("user"))
    if not participants:
        participants = list(session.participants.select_related("user"))
    profiles: list[ParticipantProfile] = []
    for participant in participants:
        try:
            intent = build_intent_text(session.quiz_snapshot, participant.quiz_answers)
        except ValueError:
            intent = ""
        vibe: list[float] | None = None
        if embed_fn is not None and intent:
            vibe = embed_fn(intent)
        elif embed_client is not None and intent:
            vibe = embed_vibe_text(intent, embed_client)
        history = positive_seed_vectors(participant.user)
        vector = blend_profile_vector(vibe, history)
        profiles.append(
            ParticipantProfile(
                participant_id=participant.id,
                user_id=participant.user_id,
                intent_text=intent,
                vector=vector,
            )
        )
    return profiles


def _excluded_movie_ids(session: LobbySession) -> set[int]:
    group_ids = set(GroupMovie.objects.filter(group=session.group).values_list("movie_id", flat=True))
    session_ids = set(session.cards.values_list("movie_id", flat=True))
    watched_ids: set[int] = set()
    active_user_ids = list(
        session.participants.filter(state=LobbyParticipant.State.ACTIVE).values_list("user_id", flat=True)
    )
    if active_user_ids:
        watched_ids = set(
            UserMovieLibrary.objects.filter(user_id__in=active_user_ids, first_watched_at__isnull=False).values_list(
                "movie_id", flat=True
            )
        )
    return group_ids | session_ids | watched_ids


def retrieve_candidates(
    profiles: list[ParticipantProfile],
    session: LobbySession,
    *,
    per_profile: int = rules.CANDIDATE_POOL_PER_PARTICIPANT,
    total_cap: int = rules.CANDIDATE_TOTAL_CAP,
) -> dict[int, list[float]]:
    """Union/dedupe pgvector cosine neighbors across profiles.

    Hard-excludes adult, group-listed, personally-watched (auto only), and
    every session card already created.
    """
    usable = [p.vector for p in profiles if p.vector is not None]
    if not usable:
        return {}
    excluded = _excluded_movie_ids(session)
    pooled: dict[int, list[float]] = {}
    for vector in usable:
        neighbors = (
            Movie.objects.filter(embeddings__isnull=False, adult=False)
            .exclude(id__in=excluded | set(pooled))
            .annotate(distance=CosineDistance("embeddings", vector))
            .order_by("distance")
            .values_list("id", "embeddings")[:per_profile]
        )
        for movie_id, embedding in neighbors:
            pooled[movie_id] = list(embedding)
            if len(pooled) >= total_cap:
                break
        if len(pooled) >= total_cap:
            break
    return pooled


def popularity_fallback(session: LobbySession, *, limit: int = rules.CANDIDATE_POOL_PER_PARTICIPANT) -> list[Movie]:
    """Deterministic fallback ordered by popularity then vote count."""
    excluded = _excluded_movie_ids(session)
    return list(
        Movie.objects.filter(adult=False).exclude(id__in=excluded).order_by("-popularity", "-vote_count", "id")[:limit]
    )


def recommend_movies(
    session: LobbySession,
    *,
    embed_client=None,
    embed_fn=None,
    per_profile: int = rules.CANDIDATE_POOL_PER_PARTICIPANT,
    total_cap: int = rules.CANDIDATE_TOTAL_CAP,
) -> list[Movie]:
    """Full pipeline: profiles -> candidates -> group-fit ranking.

    Falls back to popularity when no usable vectors exist or the recommender
    yields nothing. Never raises on embedding failure.
    """
    profiles = build_participant_profiles(session, embed_client=embed_client, embed_fn=embed_fn)
    vectors = [p.vector for p in profiles if p.vector is not None]
    if vectors:
        try:
            pooled = retrieve_candidates(profiles, session, per_profile=per_profile, total_cap=total_cap)
        except Exception:
            pooled = {}
        if pooled:
            ranked = rank_candidates(pooled, vectors)
            by_id = {m.id: m for m in Movie.objects.filter(id__in=[r.movie_id for r in ranked])}
            ordered = [by_id[r.movie_id] for r in ranked if r.movie_id in by_id]
            if ordered:
                return ordered
    return popularity_fallback(session, limit=total_cap)


def refill_session(
    session: LobbySession,
    *,
    embed_client=None,
    embed_fn=None,
) -> list[Movie]:
    """Recommend and queue; returns queued Movie objects (may be empty)."""
    from . import services as game

    movies = recommend_movies(session, embed_client=embed_client, embed_fn=embed_fn)
    if not movies:
        return []
    cards = game.queue_movies(session, movies)
    return [c.movie for c in cards]
