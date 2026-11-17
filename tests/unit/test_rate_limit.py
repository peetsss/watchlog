from typing import cast

from redis.asyncio import Redis

from app.core.rate_limit import MemoryRateLimiter, RedisRateLimiter, rate_limit_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeRedis:
    def __init__(self, count: int, ttl: int) -> None:
        self.count = count
        self.ttl = ttl

    async def eval(self, *_: object) -> list[int]:
        return [self.count, self.ttl]


def test_rate_limit_key_does_not_expose_the_identity() -> None:
    first = rate_limit_key("login", "alice@example.com")
    second = rate_limit_key("login", "bob@example.com")

    assert first != second
    assert "alice" not in first
    assert first.startswith("watchlog:rate:login:")


async def test_memory_limiter_allows_then_blocks() -> None:
    limiter = MemoryRateLimiter(clock=FakeClock())

    first = await limiter.hit("key", limit=2, window_seconds=60)
    second = await limiter.hit("key", limit=2, window_seconds=60)
    third = await limiter.hit("key", limit=2, window_seconds=60)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.remaining == 0
    assert third.retry_after == 60


async def test_memory_limiter_resets_after_the_window() -> None:
    clock = FakeClock()
    limiter = MemoryRateLimiter(clock=clock)
    await limiter.hit("key", limit=1, window_seconds=10)
    assert (await limiter.hit("key", limit=1, window_seconds=10)).allowed is False

    clock.now += 11

    assert (await limiter.hit("key", limit=1, window_seconds=10)).allowed is True


async def test_redis_limiter_maps_the_script_result() -> None:
    limiter = RedisRateLimiter(cast(Redis, FakeRedis(count=3, ttl=20)))

    result = await limiter.hit("key", limit=5, window_seconds=60)

    assert result.allowed is True
    assert result.remaining == 2
    assert result.retry_after == 20
