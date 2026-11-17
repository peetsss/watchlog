from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.guest import Guest
from app.models.lobby import Lobby, LobbyParticipant
from app.models.user import User
from app.tasks.guests import cleanup_abandoned_lobbies, cleanup_expired_guests
from app.workers.runtime import dispose_worker_runtime, init_worker_runtime


def _guest(session: Session) -> Guest:
    guest = Guest(display_name="Riley", expires_at=datetime.now(UTC) - timedelta(minutes=1))
    session.add(guest)
    session.flush()
    return guest


def _member(session: Session, username: str) -> User:
    user = User(username=username, password_hash="unused")
    session.add(user)
    session.flush()
    return user


def _lobby_with_participants(
    session: Session,
    guest: Guest,
    replacement: User | None = None,
) -> tuple[Lobby, LobbyParticipant]:
    lobby = Lobby(type="open", status="ready", pool=[], finalists=[], version=0)
    session.add(lobby)
    session.flush()
    guest_participant = LobbyParticipant(
        lobby_id=lobby.id,
        guest_id=guest.id,
        display_name=guest.display_name,
    )
    session.add(guest_participant)
    session.flush()
    lobby.host_participant_id = guest_participant.id
    if replacement is not None:
        session.add(
            LobbyParticipant(
                lobby_id=lobby.id,
                user_id=replacement.id,
                display_name=replacement.username,
            )
        )
    session.commit()
    return lobby, guest_participant


def test_expired_guest_host_transfers_the_room(
    sync_session: Session,
    test_settings: Settings,
) -> None:
    guest = _guest(sync_session)
    member = _member(sync_session, "alice")
    lobby, _ = _lobby_with_participants(sync_session, guest, member)
    lobby_id = lobby.id
    guest_id = guest.id
    init_worker_runtime(test_settings)

    try:
        deleted = cleanup_expired_guests.apply().get()
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    assert deleted == 1
    assert sync_session.get(Guest, guest_id) is None
    stored = sync_session.get(Lobby, lobby_id)
    assert stored is not None
    host = sync_session.get(LobbyParticipant, stored.host_participant_id)
    assert host is not None
    assert host.user_id == member.id


def test_expired_guest_host_with_no_replacement_deletes_the_room(
    sync_session: Session,
    test_settings: Settings,
) -> None:
    guest = _guest(sync_session)
    lobby, _ = _lobby_with_participants(sync_session, guest)
    lobby_id = lobby.id
    guest_id = guest.id
    init_worker_runtime(test_settings)

    try:
        cleanup_expired_guests.apply().get()
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    assert sync_session.get(Guest, guest_id) is None
    assert sync_session.get(Lobby, lobby_id) is None


def test_cleanup_abandoned_lobbies_only_deletes_stale_open_rooms(
    sync_session: Session,
    test_settings: Settings,
) -> None:
    stale = Lobby(
        type="open",
        status="ready",
        pool=[],
        finalists=[],
        version=0,
        updated_at=datetime.now(UTC) - timedelta(hours=25),
    )
    fresh = Lobby(type="open", status="ready", pool=[], finalists=[], version=0)
    sync_session.add_all([stale, fresh])
    sync_session.commit()
    stale_id = stale.id
    fresh_id = fresh.id
    init_worker_runtime(test_settings)

    try:
        deleted = cleanup_abandoned_lobbies.apply().get()
    finally:
        dispose_worker_runtime()

    sync_session.expire_all()
    assert deleted == 1
    assert sync_session.get(Lobby, stale_id) is None
    assert sync_session.get(Lobby, fresh_id) is not None
