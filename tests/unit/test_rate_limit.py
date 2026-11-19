from types import SimpleNamespace
from typing import cast

from redis.asyncio import Redis
from starlette.requests import Request

from app.core.rate_limit import MemoryRateLimiter, RedisRateLimiter, client_ip, rate_limit_key


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


def test_client_ip_ignores_forwarded_headers_by_default() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9"},
        client=SimpleNamespace(host="10.0.0.2"),
    )

    assert client_ip(cast(Request, request)) == "10.0.0.2"


def test_client_ip_uses_the_nearest_forwarded_hop_from_a_trusted_proxy() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9, 198.51.100.7"},
        client=SimpleNamespace(host="10.0.0.2"),
    )

    assert client_ip(cast(Request, request), ("10.0.0.2",)) == "198.51.100.7"


def test_client_ip_accepts_a_trusted_proxy_cidr() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9"},
        client=SimpleNamespace(host="10.0.0.2"),
    )

    assert client_ip(cast(Request, request), ("10.0.0.0/24",)) == "203.0.113.9"


def test_client_ip_ignores_forwarded_headers_from_an_untrusted_peer() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9"},
        client=SimpleNamespace(host="10.0.0.2"),
    )

    assert client_ip(cast(Request, request), ("10.0.0.3",)) == "10.0.0.2"


def test_client_ip_ignores_invalid_trusted_proxy_entries() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9"},
        client=SimpleNamespace(host="10.0.0.2"),
    )

    assert client_ip(cast(Request, request), ("not-an-ip", "999.1.1.1", "10.0.0.0/999")) == "10.0.0.2"


def test_client_ip_falls_back_to_the_socket_address() -> None:
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="10.0.0.2"))

    assert client_ip(cast(Request, request), ("10.0.0.2",)) == "10.0.0.2"


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
