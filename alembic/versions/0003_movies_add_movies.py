from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003_movies"
down_revision: str | None = "0002_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("imdb_id", sa.String(length=20), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_title", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(length=10), server_default="movie", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("adult", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("genres", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("director", sa.Text(), nullable=True),
        sa.Column("writers", sa.Text(), nullable=True),
        sa.Column("actors", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=10), nullable=True),
        sa.Column("spoken_languages", sa.Text(), nullable=True),
        sa.Column("production_companies", sa.Text(), nullable=True),
        sa.Column("poster_path", sa.String(length=255), nullable=True),
        sa.Column("backdrop_path", sa.String(length=255), nullable=True),
        sa.Column("awards", sa.Text(), nullable=True),
        sa.Column("revenue", sa.BigInteger(), nullable=True),
        sa.Column("budget", sa.BigInteger(), nullable=True),
        sa.Column("tmdb_score", sa.Float(), nullable=True),
        sa.Column("vote_count", sa.Integer(), nullable=True),
        sa.Column("popularity", sa.Float(), nullable=True),
        sa.Column("imdb_score", sa.Float(), nullable=True),
        sa.Column("rottentomato_score", sa.String(length=10), nullable=True),
        sa.Column("metacritic_score", sa.String(length=10), nullable=True),
        sa.Column("filmweb_score", sa.Float(), nullable=True),
        sa.Column("imdb_url", sa.Text(), nullable=True),
        sa.Column("rottentomato_url", sa.Text(), nullable=True),
        sa.Column("metacritic_url", sa.Text(), nullable=True),
        sa.Column("filmweb_url", sa.Text(), nullable=True),
        sa.Column("homepage", sa.Text(), nullable=True),
        sa.Column("embeddings", Vector(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("media_type IN ('movie', 'series')", name=op.f("ck_movies_media_type")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movies")),
        sa.UniqueConstraint("imdb_id", name=op.f("uq_movies_imdb_id")),
        sa.UniqueConstraint("tmdb_id", name=op.f("uq_movies_tmdb_id")),
    )


def downgrade() -> None:
    op.drop_table("movies")
