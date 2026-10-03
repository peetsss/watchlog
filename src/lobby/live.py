"""Post-commit channel events (no-op when Channels is not configured)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def broadcast_session(session_id: UUID | str, event: dict[str, Any]) -> None:
    """Send a lobby event to the session group. Safe to call inside on_commit."""
    try:
        from asgiref import sync
        from channels.layers import get_channel_layer
    except ImportError:
        logger.debug("channels not installed; dropping lobby event %s", event.get("type"))
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.debug("no channel layer; dropping lobby event %s", event.get("type"))
        return
    group_name = f"lobby_{session_id}"
    try:
        sync.async_to_sync(channel_layer.group_send)(group_name, event)
    except Exception:
        logger.exception("failed to broadcast lobby event %s", event.get("type"))
