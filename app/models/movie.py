from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Movie(TimestampMixin, Base):
    __tablename__ = "movies"
    __table_args__ = (
        CheckConstraint("media_type IN ('movie', 'series')", name="media_type"),
        UniqueConstraint("tmdb_id", "media_type", name="uq_movies_tmdb_media_type"),
        Index(
            "ix_movies_embeddings_hnsw",
            "embeddings",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embeddings": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer)
    imdb_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_title: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(
        String(10),
        default="movie",
        server_default="movie",
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(50))
    runtime: Mapped[int | None] = mapped_column(Integer)
    release_date: Mapped[date | None] = mapped_column(Date)
    adult: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    genres: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)
    director: Mapped[str | None] = mapped_column(Text)
    writers: Mapped[str | None] = mapped_column(Text)
    actors: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(10))
    spoken_languages: Mapped[str | None] = mapped_column(Text)
    production_companies: Mapped[str | None] = mapped_column(Text)
    poster_path: Mapped[str | None] = mapped_column(String(255))
    backdrop_path: Mapped[str | None] = mapped_column(String(255))
    awards: Mapped[str | None] = mapped_column(Text)
    revenue: Mapped[int | None] = mapped_column(BigInteger)
    budget: Mapped[int | None] = mapped_column(BigInteger)
    tmdb_score: Mapped[float | None] = mapped_column(Float)
    vote_count: Mapped[int | None] = mapped_column(Integer)
    popularity: Mapped[float | None] = mapped_column(Float)
    imdb_score: Mapped[float | None] = mapped_column(Float)
    rottentomato_score: Mapped[str | None] = mapped_column(String(10))
    metacritic_score: Mapped[str | None] = mapped_column(String(10))
    filmweb_score: Mapped[float | None] = mapped_column(Float)
    imdb_url: Mapped[str | None] = mapped_column(Text)
    rottentomato_url: Mapped[str | None] = mapped_column(Text)
    metacritic_url: Mapped[str | None] = mapped_column(Text)
    filmweb_url: Mapped[str | None] = mapped_column(Text)
    homepage: Mapped[str | None] = mapped_column(Text)
    embeddings: Mapped[list[float] | None] = mapped_column(Vector(1024))
