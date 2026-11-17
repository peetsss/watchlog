import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.celery_app import celery_app
from app.models.guest import Guest
from app.models.lobby import Lobby, LobbyParticipant
from app.workers.runtime import get_worker_runtime

logger = logging.getLogger(__name__)

ABANDONED_LOBBY_HOURS = 24


@celery_app.task(name="watchlog.guests.cleanup_expired")
def cleanup_expired_guests() -> int:
    sessionmaker_instance = get_worker_runtime().sessionmaker
    now = datetime.now(UTC)
    deleted = 0
    with sessionmaker_instance() as session:
        guests = list(
            session.scalars(
                select(Guest).where(
                    Guest.claimed_by_user_id.is_(None),
                    Guest.expires_at.is_not(None),
                    Guest.expires_at < now,
                )
            )
        )
        for guest in guests:
            participants = list(session.scalars(select(LobbyParticipant).where(LobbyParticipant.guest_id == guest.id)))
            for participant in participants:
                lobby = session.get(Lobby, participant.lobby_id)
                if lobby is None or lobby.host_participant_id != participant.id:
                    continue
                replacement = session.scalar(
                    select(LobbyParticipant)
                    .where(
                        LobbyParticipant.lobby_id == lobby.id,
                        LobbyParticipant.id != participant.id,
                    )
                    .order_by(LobbyParticipant.joined_at, LobbyParticipant.id)
                    .limit(1)
                )
                if replacement is None:
                    session.delete(lobby)
                else:
                    lobby.host_participant_id = replacement.id
            session.delete(guest)
            deleted += 1
        session.commit()
    return deleted


@celery_app.task(name="watchlog.guests.cleanup_lobbies")
def cleanup_abandoned_lobbies() -> int:
    sessionmaker_instance = get_worker_runtime().sessionmaker
    cutoff = datetime.now(UTC) - timedelta(hours=ABANDONED_LOBBY_HOURS)
    with sessionmaker_instance() as session:
        result = session.execute(
            delete(Lobby).where(
                Lobby.type == "open",
                Lobby.status.in_(("ready", "playing", "final_round")),
                Lobby.updated_at < cutoff,
            )
        )
        session.commit()
        return int(result.rowcount or 0)
