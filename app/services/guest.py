from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.guest import Guest
from app.models.lobby import Lobby, LobbyParticipant, LobbyPick, LobbyVote
from app.models.user import User
from app.services.moderation import is_allowed_name


async def create_guest(db: AsyncSession, display_name: str, ttl_seconds: int) -> Guest:
    cleaned_name = display_name.strip()
    if not is_allowed_name(cleaned_name):
        raise AppError(
            "That display name isn't allowed. Pick another one.",
            code="display_name_not_allowed",
            status_code=400,
        )
    guest = Guest(
        display_name=cleaned_name,
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )
    db.add(guest)
    await db.commit()
    await db.refresh(guest)
    return guest


async def touch_guest(db: AsyncSession, guest: Guest, ttl_seconds: int) -> None:
    now = datetime.now(UTC)
    if guest.expires_at is not None and guest.expires_at > now + timedelta(seconds=ttl_seconds // 2):
        return
    guest.expires_at = now + timedelta(seconds=ttl_seconds)
    await db.commit()


async def claim_guest(db: AsyncSession, guest_id: UUID, user: User) -> Guest | None:
    guest = await db.get(Guest, guest_id)
    if guest is None or guest.claimed_by_user_id is not None:
        return None

    participants = list(await db.scalars(select(LobbyParticipant).where(LobbyParticipant.guest_id == guest.id)))
    for participant in participants:
        existing = await db.scalar(
            select(LobbyParticipant).where(
                LobbyParticipant.lobby_id == participant.lobby_id,
                LobbyParticipant.user_id == user.id,
            )
        )
        if existing is None:
            participant.user_id = user.id
            participant.guest_id = None
            participant.display_name = user.username
            continue

        existing.is_ready = existing.is_ready or participant.is_ready
        lobby = await db.get(Lobby, participant.lobby_id)
        if lobby is not None and lobby.host_participant_id == participant.id:
            lobby.host_participant_id = existing.id

        guest_votes = list(await db.scalars(select(LobbyVote).where(LobbyVote.participant_id == participant.id)))
        for vote in guest_votes:
            already_voted = await db.scalar(
                select(LobbyVote).where(
                    LobbyVote.lobby_id == vote.lobby_id,
                    LobbyVote.movie_id == vote.movie_id,
                    LobbyVote.participant_id == existing.id,
                )
            )
            if already_voted is not None:
                await db.delete(vote)
            else:
                vote.participant_id = existing.id

        guest_pick = await db.scalar(select(LobbyPick).where(LobbyPick.participant_id == participant.id))
        if guest_pick is not None:
            existing_pick = await db.scalar(select(LobbyPick).where(LobbyPick.participant_id == existing.id))
            if existing_pick is None:
                guest_pick.participant_id = existing.id
            else:
                await db.delete(guest_pick)

        await db.delete(participant)

    guest.claimed_by_user_id = user.id
    guest.expires_at = None
    await db.commit()
    return guest
