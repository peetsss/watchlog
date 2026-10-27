from typing import Final

FINALIST_COUNT: Final[int] = 10
POOL_SIZE: Final[int] = 100

GROUP_LOBBY: Final[str] = "group"
OPEN_LOBBY: Final[str] = "open"

HOST_ROLE: Final[str] = "host"
MEMBER_ROLE: Final[str] = "member"

READY: Final[str] = "ready"
PLAYING: Final[str] = "playing"
FINAL_ROUND: Final[str] = "final_round"
FINISHED: Final[str] = "finished"

ACTIVE_STATUSES: Final[frozenset[str]] = frozenset({READY, PLAYING, FINAL_ROUND})

INTERESTED: Final[str] = "interested"
WATCHED: Final[str] = "watched"
NOT_INTERESTED: Final[str] = "not_interested"
PICK: Final[str] = "pick"

VOTE_CHOICES: Final[frozenset[str]] = frozenset({INTERESTED, WATCHED, NOT_INTERESTED})
