import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.services.embeddings import (  # noqa: E402
    EMBED_DIMENSIONS,
    EMBED_MODEL,
    OLLAMA_URL,
    backfill_embeddings,
    build_movie_document,
)

ANCHOR_TMDB_ID = 27205


def run_dry_run(session: Session, limit: int) -> None:
    movies = list(session.scalars(select(Movie).order_by(Movie.tmdb_id).limit(limit)))
    if not movies:
        print("dry run: no movies in database")
        return
    for movie in movies[:3]:
        document = build_movie_document(movie)
        print(f"--- tmdb_id={movie.tmdb_id} chars={len(document)} ---")
        print(document)
    print(f"dry run: built {len(movies)} documents, called nothing")


def run_verify(session: Session) -> None:
    total = session.scalar(select(func.count()).select_from(Movie)) or 0
    embedded = session.scalar(select(func.count()).select_from(Movie).where(Movie.embeddings.is_not(None))) or 0
    print(f"verify: {embedded}/{total} movies embedded")

    first = session.scalars(select(Movie).where(Movie.embeddings.is_not(None)).order_by(Movie.tmdb_id)).first()
    if first is not None:
        print(f"verify: sample tmdb_id={first.tmdb_id} dims={len(first.embeddings)}")

    anchor = session.scalars(
        select(Movie).where(Movie.tmdb_id == ANCHOR_TMDB_ID, Movie.embeddings.is_not(None))
    ).first()
    if anchor is None:
        print(f"verify: tmdb_id {ANCHOR_TMDB_ID} is not embedded, skipping neighbor check")
        return

    if anchor.embeddings is None:
        print(f"verify: could not load the vector for {anchor.title}")
        return
    vector = [float(value) for value in anchor.embeddings]
    neighbors = session.execute(
        text(
            """
            SELECT tmdb_id, title, round((embeddings <=> CAST(:vector AS vector))::numeric, 4) AS distance
            FROM movies
            WHERE embeddings IS NOT NULL AND id <> :id
            ORDER BY embeddings <=> CAST(:vector AS vector)
            LIMIT 5
            """
        ),
        {"vector": str(vector), "id": anchor.id},
    ).fetchall()
    print(f"verify: nearest neighbors of {anchor.title} ({anchor.tmdb_id}):")
    for neighbor in neighbors:
        print(f"  {neighbor.title} ({neighbor.tmdb_id}) distance={neighbor.distance}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill movie embeddings from Ollama.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", OLLAMA_URL))
    parser.add_argument("--model", default=EMBED_MODEL)
    parser.add_argument("--dimensions", type=int, default=EMBED_DIMENSIONS)
    parser.add_argument("--ollama-timeout", type=float, default=600.0)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.dimensions != EMBED_DIMENSIONS:
        raise SystemExit(f"--dimensions ({args.dimensions}) must match the embeddings column ({EMBED_DIMENSIONS})")

    settings = Settings()
    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    with Session(engine) as session:
        if args.dry_run:
            run_dry_run(session, args.limit or 5)
            return
        if args.verify:
            run_verify(session)
            return

        with httpx.Client() as client:
            stats = backfill_embeddings(
                session,
                client,
                ollama_url=args.ollama_url,
                model=args.model,
                dimensions=args.dimensions,
                batch_size=args.batch_size,
                limit=args.limit,
                timeout=args.ollama_timeout,
                progress=print,
            )
    print(f"done: processed={stats['processed']} embedded={stats['embedded']}")


if __name__ == "__main__":
    main()
