"""Versioned vibe-quiz pool, snapshots, validation, and intent text.

Classic selects three questions once per session; every participant answers
the same questions independently. Answers describe intent/mood and must not
be collapsed by majority vote. Snapshots are stored on the session so saved
answers stay interpretable if the pool changes later.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .rules import QUIZ_QUESTION_COUNT, QUIZ_VERSION


@dataclass(frozen=True, slots=True)
class QuizOption:
    key: str
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    id: str
    text: str
    options: tuple[QuizOption, ...]


# Versioned pool in code. Keys/IDs are stable; text may evolve under a new version.
QUESTION_POOL_V1: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        id="energy",
        text="What energy are you in the mood for?",
        options=(
            QuizOption("light", "Light & fun", "something light, playful, and easy to watch"),
            QuizOption("balanced", "Balanced", "something engaging but not exhausting"),
            QuizOption("intense", "Intense", "something intense, gripping, and immersive"),
        ),
    ),
    QuizQuestion(
        id="pace",
        text="What pace should the night have?",
        options=(
            QuizOption("cozy", "Cozy & slow", "a slow, cozy, atmospheric pace"),
            QuizOption("steady", "Steady", "a steady pace with momentum but room to breathe"),
            QuizOption("fast", "Fast & propulsive", "a fast, propulsive, edge-of-seat pace"),
        ),
    ),
    QuizQuestion(
        id="tone",
        text="What emotional tone fits tonight?",
        options=(
            QuizOption("uplifting", "Uplifting", "an uplifting, hopeful emotional tone"),
            QuizOption("bittersweet", "Bittersweet", "a bittersweet, reflective emotional tone"),
            QuizOption("dark", "Dark", "a dark, heavy, cathartic emotional tone"),
        ),
    ),
    QuizQuestion(
        id="openness",
        text="How adventurous should the pick be?",
        options=(
            QuizOption("comfort", "Comfort zone", "a familiar comfort-zone genre and style"),
            QuizOption("curious", "Curious", "something a little outside the usual comfort zone"),
            QuizOption("wild", "Wild card", "a bold wild-card pick we would never choose alone"),
        ),
    ),
    QuizQuestion(
        id="company",
        text="What should the movie give this group?",
        options=(
            QuizOption("laugh", "Laugh together", "plenty to laugh about together"),
            QuizOption("talk", "Talk about after", "something to discuss long after it ends"),
            QuizOption("escape", "Pure escape", "pure escapism with no homework feeling"),
        ),
    ),
)

_POOLS: dict[str, tuple[QuizQuestion, ...]] = {"v1": QUESTION_POOL_V1}


def get_question_pool(version: str = QUIZ_VERSION) -> tuple[QuizQuestion, ...]:
    """Return the versioned question pool; raise on unknown version."""
    try:
        return _POOLS[version]
    except KeyError:
        raise ValueError(f"Unknown quiz version: {version!r}") from None


def select_quiz_snapshot(seed: UUID | str | int | None = None) -> dict[str, Any]:
    """Select one shared snapshot of `QUIZ_QUESTION_COUNT` questions.

    Deterministic when `seed` is given (UUID/str/int); random otherwise.
    The snapshot is JSON-serializable and stored on the session.
    """
    pool = get_question_pool(QUIZ_VERSION)
    rng = random.Random(int(seed) if isinstance(seed, int) else str(seed) if seed is not None else None)
    # random.Random(None) seeds from OS entropy; Random(str) is deterministic per process.
    picked = rng.sample(list(pool), QUIZ_QUESTION_COUNT)
    return {
        "version": QUIZ_VERSION,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "options": [{"key": o.key, "label": o.label, "description": o.description} for o in q.options],
            }
            for q in picked
        ],
    }


def snapshot_question_ids(snapshot: dict[str, Any]) -> list[str]:
    """Stable question IDs in snapshot order."""
    return [q["id"] for q in snapshot.get("questions", [])]


def validate_quiz_answers(snapshot: dict[str, Any], answers: dict[str, str]) -> dict[str, str]:
    """Validate `answers` ({question_id: option_key}) against `snapshot`.

    Requires every snapshot question to be answered exactly once with a key
    from that question's options. Returns a normalized copy. Raises
    ValueError on any mismatch; never mutates inputs.
    """
    if not isinstance(answers, dict):
        raise ValueError("quiz answers must be a mapping of question id to option key")
    questions = {q["id"]: q for q in snapshot.get("questions", [])}
    if set(answers) != set(questions):
        missing = set(questions) - set(answers)
        extra = set(answers) - set(questions)
        parts: list[str] = []
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        if extra:
            parts.append(f"unknown: {sorted(extra)}")
        raise ValueError(f"answers must cover exactly the session questions ({'; '.join(parts)})")
    normalized: dict[str, str] = {}
    for qid, key in answers.items():
        valid_keys = {o["key"] for o in questions[qid]["options"]}
        if key not in valid_keys:
            raise ValueError(f"invalid option {key!r} for question {qid!r}; expected one of {sorted(valid_keys)}")
        normalized[qid] = key
    return normalized


def build_intent_text(snapshot: dict[str, Any], answers: dict[str, str]) -> str:
    """Compose a per-participant session intent string from answer descriptions.

    Individual differences are preserved: the text reflects only this
    participant's selections, in snapshot question order.
    """
    validated = validate_quiz_answers(snapshot, answers)
    by_id = {q["id"]: q for q in snapshot.get("questions", [])}
    phrases: list[str] = []
    for qid in snapshot_question_ids(snapshot):
        question = by_id[qid]
        option = next(o for o in question["options"] if o["key"] == validated[qid])
        phrases.append(option["description"])
    joined = "; ".join(phrases)
    return f"Tonight we want a movie that is {joined}." if joined else ""
