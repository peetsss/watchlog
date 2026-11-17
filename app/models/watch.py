from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MovieWatchRegion(Base):
    __tablename__ = "movie_watch_regions"
    __table_args__ = (
        CheckConstraint("region ~ '^[A-Z]{2}$'", name="region"),
        Index("ix_movie_watch_regions_region_fetched", "region", "fetched_at"),
        Index("ix_movie_watch_regions_region_offers", "region", "offer_count"),
    )

    movie_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    region: Mapped[str] = mapped_column(String(2), primary_key=True)
    tmdb_link: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    offer_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class MovieWatchProvider(Base):
    __tablename__ = "movie_watch_providers"
    __table_args__ = (
        CheckConstraint("region ~ '^[A-Z]{2}$'", name="region"),
        CheckConstraint(
            "offer_type IN ('flatrate','free','ads','rent','buy')",
            name="offer_type",
        ),
        ForeignKeyConstraint(
            ["movie_id", "region"],
            ["movie_watch_regions.movie_id", "movie_watch_regions.region"],
            ondelete="CASCADE",
        ),
        Index("ix_movie_watch_providers_region_offer_provider", "region", "offer_type", "provider_id"),
        Index("ix_movie_watch_providers_movie", "movie_id"),
    )

    movie_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    region: Mapped[str] = mapped_column(String(2), primary_key=True)
    offer_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    provider_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    logo_path: Mapped[str | None] = mapped_column(Text)
    display_priority: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000", nullable=False)


__all__ = ["MovieWatchProvider", "MovieWatchRegion"]
