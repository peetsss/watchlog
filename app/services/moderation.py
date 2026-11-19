import re
import unicodedata

RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "admin",
        "administrator",
        "billing",
        "help",
        "mod",
        "moderator",
        "official",
        "owner",
        "root",
        "security",
        "staff",
        "support",
        "system",
        "watchlog",
    }
)

BLOCKED_TERMS: frozenset[str] = frozenset(
    {
        "asshole",
        "bastard",
        "bitch",
        "bullshit",
        "cunt",
        "dick",
        "fag",
        "faggot",
        "fuck",
        "nazi",
        "nigga",
        "nigger",
        "piss",
        "prick",
        "retard",
        "shit",
        "slut",
        "twat",
        "whore",
    }
)

_LEET_REPLACEMENTS = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "!": "i",
    }
)
_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


def _normalized_tokens(value: str) -> tuple[str, list[str]]:
    normalized = unicodedata.normalize("NFKC", value).casefold().translate(_LEET_REPLACEMENTS)
    compact = _SEPARATOR_PATTERN.sub("", normalized)
    tokens = [token for token in _SEPARATOR_PATTERN.split(normalized) if token]
    return compact, tokens


def is_allowed_name(value: str) -> bool:
    compact, tokens = _normalized_tokens(value)
    if not compact:
        return False
    if any(ord(character) < 32 for character in value):
        return False
    if "://" in value or "www." in value.casefold():
        return False
    if any(token in RESERVED_NAMES or token in BLOCKED_TERMS for token in tokens):
        return False
    if any(compact.startswith(term) or compact.endswith(term) for term in RESERVED_NAMES | BLOCKED_TERMS):
        return False
    return True
