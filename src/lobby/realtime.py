import logging
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def lobby_group_name(lobby_uuid: str | UUID) -> str:
    return f"lobby_{lobby_uuid}"


def notify_lobby_changed(lobby_uuid: str | UUID, version: int, reason: str) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            lobby_group_name(lobby_uuid),
            {
                "type": "lobby.changed",
                "lobby_uuid": str(lobby_uuid),
                "version": version,
                "reason": reason,
            },
        )
    except Exception:
        logger.exception("Failed to broadcast lobby change for %s", lobby_uuid)


def notify_lobby_restarted(lobby_uuid: str | UUID, new_lobby_uuid: str | UUID) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            lobby_group_name(lobby_uuid),
            {
                "type": "lobby.restarted",
                "lobby_uuid": str(lobby_uuid),
                "new_lobby_uuid": str(new_lobby_uuid),
            },
        )
    except Exception:
        logger.exception("Failed to broadcast lobby restart for %s", lobby_uuid)


def schedule_lobby_changed(lobby_uuid: str | UUID, version: int, reason: str) -> None:
    transaction.on_commit(lambda: notify_lobby_changed(lobby_uuid, version, reason))


def schedule_lobby_restarted(lobby_uuid: str | UUID, new_lobby_uuid: str | UUID) -> None:
    transaction.on_commit(lambda: notify_lobby_restarted(lobby_uuid, new_lobby_uuid))
