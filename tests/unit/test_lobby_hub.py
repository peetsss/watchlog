from uuid import uuid4

from app.realtime.events import LobbyChanged, LobbyRestarted
from app.realtime.hub import MemoryLobbyHub, deserialize_event, serialize_event


async def test_memory_hub_dispatches_and_unregisters() -> None:
    hub = MemoryLobbyHub()
    lobby_id = uuid4()
    received = []

    async def callback(event: object) -> None:
        received.append(event)

    event = LobbyChanged(lobby_id, 3, "vote")
    await hub.register(lobby_id, callback)
    await hub.publish(event)

    assert received == [event]

    await hub.unregister(lobby_id, callback)
    await hub.publish(LobbyChanged(lobby_id, 4, "vote"))

    assert len(received) == 1


def test_events_round_trip() -> None:
    changed = LobbyChanged(uuid4(), 7, "ready")
    restarted = LobbyRestarted(uuid4(), uuid4())

    assert deserialize_event(serialize_event(changed)) == changed
    assert deserialize_event(serialize_event(restarted)) == restarted
    assert deserialize_event("not json") is None
    assert deserialize_event('{"type": "unknown"}') is None
