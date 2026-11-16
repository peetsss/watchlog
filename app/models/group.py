import uuid
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="role"),
        Index("ix_group_memberships_user_id", "user_id"),
    )

    group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(10), default="member", server_default="member", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class GroupMovie(Base):
    __tablename__ = "group_movies"
    __table_args__ = (
        UniqueConstraint("group_id", "movie_id", name="uq_group_movies_group_movie"),
        CheckConstraint("status IN ('up_next', 'watched')", name="status"),
        Index("ix_group_movies_group_id", "group_id"),
        Index("ix_group_movies_movie_id", "movie_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    movie_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    suggested_by_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(10), default="up_next", server_default="up_next", nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("group_movie_id", "user_id", name="uq_reviews_group_movie_user"),
        CheckConstraint("score >= 1 AND score <= 10", name="score_range"),
        Index("ix_reviews_group_movie_id", "group_movie_id"),
        Index("ix_reviews_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_movie_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("group_movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    contains_spoilers: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
