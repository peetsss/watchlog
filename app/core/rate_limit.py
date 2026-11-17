import hashlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol, cast

from redis.asyncio import Redis

RATE_LIMIT_PREFIX: Final[str] = "watchlog:rate:"
_IDENTITY_HASH_LENGTH: Final[int] = 32

_FIXED_WINDOW_SCRIPT: Final[str] = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult: ...


def rate_limit_key(bucket: str, identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:_IDENTITY_HASH_LENGTH]
    return f"{RATE_LIMIT_PREFIX}{bucket}:{digest}"


def _result(count: int, ttl: int, limit: int) -> RateLimitResult:
    return RateLimitResult(
        allowed=count <= limit,
        limit=limit,
        remaining=max(limit - count, 0),
        retry_after=max(ttl, 0),
    )


class RedisRateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        raw = await self._redis.eval(_FIXED_WINDOW_SCRIPT, 1, key, window_seconds)
        count, ttl = cast(list[int], raw)
        return _result(int(count), int(ttl), limit)


class MemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[int, float]] = {}

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = self._clock()
        count, expires_at = self._entries.get(key, (0, now + window_seconds))
        if now >= expires_at:
            count = 0
            expires_at = now + window_seconds
        count += 1
        self._entries[key] = (count, expires_at)
        ttl = math.ceil(expires_at - now)
        return _result(count, ttl, limit)
