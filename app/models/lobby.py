import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Lobby(TimestampMixin, Base):
    __tablename__ = "lobbies"
    __table_args__ = (
        CheckConstraint("type IN ('group', 'open')", name="type"),
        CheckConstraint("status IN ('ready', 'playing', 'final_round', 'finished')", name="status"),
        CheckConstraint(
            "(type = 'group' AND group_id IS NOT NULL) OR (type = 'open' AND group_id IS NULL)",
            name="group_matches_type",
        ),
        Index(
            "uq_lobbies_active_group",
            "group_id",
            unique=True,
            postgresql_where=text("status IN ('ready', 'playing', 'final_round')"),
        ),
        Index("ix_lobbies_status", "status"),
        Index("ix_lobbies_group_status", "group_id", "status"),
        Index("ix_lobbies_host_participant_id", "host_participant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
    )
    type: Mapped[str] = mapped_column(String(8), default="open", server_default="open", nullable=False)
    host_participant_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(12), default="ready", server_default="ready", nullable=False)
    pool: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False)
    pool_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    finalists: Mapped[list[int]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    winner_movie_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("movies.id", ondelete="RESTRICT"),
    )
    revealed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    picks_revealed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LobbyParticipant(Base):
    __tablename__ = "lobby_participants"
    __table_args__ = (
        Index(
            "uq_lobby_participants_user",
            "lobby_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_lobby_participants_guest",
            "lobby_id",
            "guest_id",
            unique=True,
            postgresql_where=text("guest_id IS NOT NULL"),
        ),
        CheckConstraint("num_nonnulls(user_id, guest_id) = 1", name="identity"),
        Index("ix_lobby_participants_lobby_id", "lobby_id"),
        Index("ix_lobby_participants_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lobby_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lobbies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    guest_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("guests.id", ondelete="CASCADE"),
    )
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LobbyVote(Base):
    __tablename__ = "lobby_votes"
    __table_args__ = (
        CheckConstraint("choice IN ('interested', 'watched', 'not_interested')", name="choice"),
        Index("ix_lobby_votes_participant_id", "participant_id"),
    )

    lobby_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lobbies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    movie_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("movies.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lobby_participants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    choice: Mapped[str] = mapped_column(String(15), nullable=False)


class LobbyPick(Base):
    __tablename__ = "lobby_picks"
    __table_args__ = (Index("ix_lobby_picks_participant_id", "participant_id"),)

    lobby_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lobbies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lobby_participants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    movie_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False,
    )
