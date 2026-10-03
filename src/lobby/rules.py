"""Classic v1 rule constants.

Versioned data, not a plugin system. Tune values after use; keep them
named and configurable here so recommender/services import from one place.
Do not add host-editable rules UI in Classic v1.
"""

RULES_VERSION = "classic-v1"
QUIZ_VERSION = "v1"

# §13 proposed initial values.
QUIZ_QUESTION_COUNT = 3
MAX_QUEUED_CARDS = 30
MAX_RESOLVED_CARDS = 80
MIN_PARTICIPANTS_TO_START = 2

# §4.2: high-scored review threshold for positive history centroid.
HISTORY_SCORE_THRESHOLD = 7

# §4.2: query-only vibe embedding instruction (do not re-embed documents).
VIBE_TASK = "Given a movie night mood description, retrieve movies that fit the vibe, energy, pace, and emotional tone"
VIBE_EMBED_DIMENSIONS = 1024

# §4.3: group-fit ranking = mean fit - DISAGREEMENT_PENALTY_WEIGHT * std.
DISAGREEMENT_PENALTY_WEIGHT = 0.5
CANDIDATE_POOL_PER_PARTICIPANT = 50
CANDIDATE_TOTAL_CAP = 120
