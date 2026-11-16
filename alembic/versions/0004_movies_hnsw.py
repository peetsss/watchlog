from collections.abc import Sequence

from alembic import op

revision: str = "0004_movies_hnsw"
down_revision: str | None = "0003_movies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_movies_embeddings_hnsw",
        "movies",
        ["embeddings"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embeddings": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_movies_embeddings_hnsw", table_name="movies")
