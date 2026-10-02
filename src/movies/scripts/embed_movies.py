import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "watchlog.settings.dev")

import django

django.setup()

import httpx  # noqa: E402
from pgvector.django import CosineDistance  # noqa: E402

from movies.models import Movie  # noqa: E402
from movies.utils.embeddings import (  # noqa: E402
    EMBED_DIMENSIONS,
    EMBED_MODEL,
    OLLAMA_URL,
    backfill_embeddings,
    build_movie_document,
)


def run_dry_run(limit: int) -> None:
    movies = list(Movie.objects.order_by("tmdb_id")[:limit])
    if not movies:
        print("dry run: no movies in database")
        return
    for movie in movies[:3]:
        document = build_movie_document(movie)
        print(f"--- tmdb_id={movie.tmdb_id} chars={len(document)} ---")
        print(document)
    print(f"dry run: built {len(movies)} documents, called nothing")


def run_verify() -> None:
    null_count = Movie.objects.filter(embeddings__isnull=True).count()
    total = Movie.objects.count()
    print(f"verify: {total - null_count}/{total} movies embedded")
    first = Movie.objects.filter(embeddings__isnull=False).order_by("tmdb_id").first()
    if first is not None:
        print(f"verify: sample tmdb_id={first.tmdb_id} dims={len(first.embeddings)}")
    dune = Movie.objects.filter(embeddings__isnull=False, tmdb_id=27205).first()
    if dune is None:
        print("verify: Dune (27205) not embedded, skipping neighbor check")
        return
    neighbors = (
        Movie.objects.filter(embeddings__isnull=False)
        .exclude(pk=dune.pk)
        .annotate(distance=CosineDistance("embeddings", list(dune.embeddings)))
        .order_by("distance")[:5]
    )
    print("verify: nearest neighbors of Dune (27205):")
    for neighbor in neighbors:
        print(f"  {neighbor.title} ({neighbor.tmdb_id}) distance={neighbor.distance:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill movie embeddings from Ollama.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", OLLAMA_URL))
    parser.add_argument("--model", default=EMBED_MODEL)
    parser.add_argument("--dimensions", type=int, default=EMBED_DIMENSIONS)
    parser.add_argument("--ollama-timeout", type=float, default=600.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.dimensions != EMBED_DIMENSIONS:
        raise SystemExit(f"--dimensions ({args.dimensions}) must match the embeddings column ({EMBED_DIMENSIONS})")

    if args.dry_run:
        run_dry_run(args.limit or 5)
        return

    if args.verify:
        run_verify()
        return

    with httpx.Client() as client:
        stats = backfill_embeddings(
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
