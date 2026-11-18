from types import SimpleNamespace

from app.core.rate_limit import MemoryRateLimiter
from app.models.user import User
from app.realtime.ws_lobby import _action_allowed
from app.services.identity import Viewer


def _websocket(limiter: MemoryRateLimiter, *, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                rate_limiter=limiter,
                settings=SimpleNamespace(rate_limit_enabled=enabled),
            )
        )
    )


async def test_websocket_action_bucket_allows_then_blocks() -> None:
    limiter = MemoryRateLimiter()
    websocket = _websocket(limiter)
    viewer = Viewer.for_user(User(id=1, username="alice", password_hash="unused"))

    assert all([await _action_allowed(websocket, viewer) for _ in range(120)])
    assert await _action_allowed(websocket, viewer) is False


async def test_websocket_action_bucket_is_skipped_when_limits_are_disabled() -> None:
    websocket = _websocket(MemoryRateLimiter(), enabled=False)
    viewer = Viewer.for_user(User(id=1, username="alice", password_hash="unused"))

    assert all([await _action_allowed(websocket, viewer) for _ in range(130)])
