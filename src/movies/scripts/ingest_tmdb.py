import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "watchlog.settings.dev")

import django

django.setup()

from movies.models import Movie  # noqa: E402
from movies.utils.tmdb import BACKDROP_BASE_URL, POSTER_BASE_URL  # noqa: E402


def _to_int_or_none(value: str | None) -> int | None:
    value = (value or "").strip()
    if value in ("", "0"):
        return None
    return int(value)


def _to_float_or_none(value: str | None) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def _parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _split_names(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _join_names(names: list[str]) -> str | None:
    return ", ".join(names) if names else None


@dataclass
class MovieRow:
    tmdb_id: int
    title: str
    vote_average: float | None
    vote_count: int
    status: str
    release_date: date | None
    revenue: int | None
    runtime: int | None
    adult: bool
    backdrop_path: str | None
    budget: int | None
    imdb_id: str | None
    original_title: str | None
    overview: str
    popularity: float | None
    poster_path: str | None
    tagline: str | None
    homepage: str | None
    original_language: str | None
    genres: list[str]
    production_companies: list[str]
    production_countries: list[str]
    spoken_languages: list[str]
    keywords: list[str]

    @classmethod
    def from_row(cls, row: dict[str, str], min_votes: int = 0) -> "MovieRow | None":
        if (row.get("status") or "").strip() != "Released":
            return None
        overview = (row.get("overview") or "").strip()
        if not overview:
            return None
        vote_count = int(row.get("vote_count") or 0)
        if vote_count < min_votes:
            return None
        title = (row.get("title") or "").strip()
        if not title:
            raise ValueError("missing title")
        imdb_id = (row.get("imdb_id") or "").strip() or None
        if imdb_id == "0":
            imdb_id = None
        return cls(
            tmdb_id=int(row["id"]),
            title=title,
            vote_average=_to_float_or_none(row.get("vote_average")),
            vote_count=vote_count,
            status="Released",
            release_date=_parse_date(row.get("release_date")),
            revenue=_to_int_or_none(row.get("revenue")),
            runtime=_to_int_or_none(row.get("runtime")),
            adult=(row.get("adult") or "").strip() == "True",
            backdrop_path=(row.get("backdrop_path") or "").strip() or None,
            budget=_to_int_or_none(row.get("budget")),
            imdb_id=imdb_id,
            original_title=(row.get("original_title") or "").strip() or None,
            overview=overview,
            popularity=_to_float_or_none(row.get("popularity")),
            poster_path=(row.get("poster_path") or "").strip() or None,
            tagline=(row.get("tagline") or "").strip() or None,
            homepage=(row.get("homepage") or "").strip() or None,
            original_language=(row.get("original_language") or "").strip() or None,
            genres=_split_names(row.get("genres")),
            production_companies=_split_names(row.get("production_companies")),
            production_countries=_split_names(row.get("production_countries")),
            spoken_languages=_split_names(row.get("spoken_languages")),
            keywords=_split_names(row.get("keywords")),
        )

    def to_model(self) -> Movie:
        imdb_url = f"https://www.imdb.com/title/{self.imdb_id}" if self.imdb_id else None
        return Movie(
            tmdb_id=self.tmdb_id,
            imdb_id=self.imdb_id,
            title=self.title,
            original_title=self.original_title,
            media_type=Movie.MediaType.MOVIE,
            description=self.overview,
            tagline=self.tagline,
            status=self.status,
            runtime=self.runtime,
            release_date=self.release_date,
            adult=self.adult,
            genres=_join_names(self.genres),
            keywords=_join_names(self.keywords),
            country=_join_names(self.production_countries),
            original_language=self.original_language,
            spoken_languages=_join_names(self.spoken_languages),
            production_companies=_join_names(self.production_companies),
            poster_path=POSTER_BASE_URL + self.poster_path if self.poster_path else None,
            backdrop_path=BACKDROP_BASE_URL + self.backdrop_path if self.backdrop_path else None,
            tmdb_score=self.vote_average,
            vote_count=self.vote_count,
            popularity=self.popularity,
            revenue=self.revenue,
            budget=self.budget,
            imdb_url=imdb_url,
            homepage=self.homepage,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk ingest movies from the TMDB CSV dataset.")
    parser.add_argument(
        "--csv-path",
        default=str(Path(__file__).resolve().parent.parent.parent.parent / "TMDB_movie_dataset_v11.csv"),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-votes", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        raise SystemExit(f"CSV file not found: {csv_path}")

    existing: set[int] = set()
    if not args.dry_run:
        existing = set(Movie.objects.values_list("tmdb_id", flat=True))

    processed = submitted = skipped_filtered = skipped_malformed = skipped_existing = 0
    batch: list[Movie] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if args.limit is not None and processed >= args.limit:
                break
            processed += 1
            try:
                parsed = MovieRow.from_row(row, min_votes=args.min_votes)
            except KeyError, TypeError, ValueError:
                skipped_malformed += 1
                continue
            if parsed is None:
                skipped_filtered += 1
                continue
            if parsed.tmdb_id in existing:
                skipped_existing += 1
                continue
            existing.add(parsed.tmdb_id)
            batch.append(parsed.to_model())
            if len(batch) >= args.batch_size:
                if not args.dry_run:
                    Movie.objects.bulk_create(batch, ignore_conflicts=True)
                submitted += len(batch)
                batch.clear()
            if processed % 100000 == 0:
                print(f"processed {processed} rows...")

    if batch:
        if not args.dry_run:
            Movie.objects.bulk_create(batch, ignore_conflicts=True)
        submitted += len(batch)

    print(
        f"done: processed={processed} submitted={submitted} "
        f"filtered={skipped_filtered} malformed={skipped_malformed} "
        f"existing={skipped_existing} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
