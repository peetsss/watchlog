import argparse
import sys
from pathlib import Path
from typing import Final

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings  # noqa: E402

SOURCE_DATABASE: Final[str] = "watchlog_db"
TARGET_DATABASE: Final[str] = "watchlog_v2"
SOURCE_TABLE: Final[str] = "movies_movie"
TARGET_TABLE: Final[str] = "movies"
SAMPLE_SIZE: Final[int] = 100
NEIGHBOR_TMDB_ID: Final[int] = 27205

MOVIE_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "tmdb_id",
    "imdb_id",
    "title",
    "original_title",
    "media_type",
    "description",
    "tagline",
    "status",
    "runtime",
    "release_date",
    "adult",
    "genres",
    "keywords",
    "director",
    "writers",
    "actors",
    "country",
    "original_language",
    "spoken_languages",
    "production_companies",
    "poster_path",
    "backdrop_path",
    "awards",
    "revenue",
    "budget",
    "tmdb_score",
    "vote_count",
    "popularity",
    "imdb_score",
    "rottentomato_score",
    "metacritic_score",
    "filmweb_score",
    "imdb_url",
    "rottentomato_url",
    "metacritic_url",
    "filmweb_url",
    "homepage",
    "embeddings",
)


def _database_url(settings: Settings, database: str) -> str:
    return (
        make_url(settings.sqlalchemy_url)
        .set(drivername="postgresql", database=database)
        .render_as_string(hide_password=False)
    )


def _table(name: str) -> sql.Composed:
    return sql.SQL("{}.{}").format(sql.Identifier("public"), sql.Identifier(name))


def _copy(source: psycopg.Connection, target: psycopg.Connection, source_table: str) -> None:
    select_columns = sql.SQL(", ").join(sql.Identifier(column) for column in MOVIE_COLUMNS)
    export = sql.SQL("COPY (SELECT {} FROM {}) TO STDOUT WITH (FORMAT csv)").format(
        select_columns,
        _table(source_table),
    )
    insert_columns = sql.SQL(", ").join(sql.Identifier(column) for column in MOVIE_COLUMNS)
    import_statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
        _table(TARGET_TABLE),
        insert_columns,
    )

    with source.cursor() as source_cursor, target.cursor() as target_cursor:
        with source_cursor.copy(export) as copy_out, target_cursor.copy(import_statement) as copy_in:
            while chunk := copy_out.read():
                copy_in.write(chunk)
    target.commit()


def _counts(connection: psycopg.Connection, table: str) -> tuple[int, int]:
    query = sql.SQL("SELECT count(*), count(embeddings) FROM {}").format(_table(table))
    row = connection.execute(query).fetchone()
    if row is None:
        raise RuntimeError(f"Could not count {table}")
    return int(row[0]), int(row[1])


def _invalid_dimensions(connection: psycopg.Connection, table: str) -> int:
    query = sql.SQL("SELECT count(*) FROM {} WHERE embeddings IS NOT NULL AND vector_dims(embeddings) <> 1024").format(
        _table(table)
    )
    row = connection.execute(query).fetchone()
    if row is None:
        raise RuntimeError(f"Could not inspect {table}")
    return int(row[0])


def _sample_hashes(connection: psycopg.Connection, table: str, descending: bool) -> dict[int, str]:
    ordering = sql.SQL("DESC") if descending else sql.SQL("ASC")
    query = sql.SQL(
        "SELECT id, md5(embeddings::text) FROM {} WHERE embeddings IS NOT NULL ORDER BY id {} LIMIT %s"
    ).format(_table(table), ordering)
    return {int(row[0]): str(row[1]) for row in connection.execute(query, (SAMPLE_SIZE,)).fetchall()}


def _neighbors(connection: psycopg.Connection, table: str) -> list[tuple[int, str, str]]:
    query = sql.SQL(
        """
        WITH target AS (SELECT embeddings FROM {} WHERE tmdb_id = %s)
        SELECT m.tmdb_id, m.title, round((m.embeddings <=> target.embeddings)::numeric, 6)
        FROM {} AS m, target
        WHERE m.embeddings IS NOT NULL AND m.tmdb_id IS DISTINCT FROM %s
        ORDER BY m.embeddings <=> target.embeddings
        LIMIT 5
        """
    ).format(_table(table), _table(table))
    rows = connection.execute(query, (NEIGHBOR_TMDB_ID, NEIGHBOR_TMDB_ID)).fetchall()
    return [(int(row[0]), str(row[1]), str(row[2])) for row in rows]


def _verify(source: psycopg.Connection, target: psycopg.Connection, source_table: str) -> None:
    source_counts = _counts(source, source_table)
    target_counts = _counts(target, TARGET_TABLE)
    print(f"source: {source_counts[0]} movies, {source_counts[1]} embedded")
    print(f"target: {target_counts[0]} movies, {target_counts[1]} embedded")

    failures: list[str] = []
    if source_counts != target_counts:
        failures.append("row or embedding counts differ")
    if _invalid_dimensions(target, TARGET_TABLE) != 0:
        failures.append("target contains vectors that are not 1024 dimensions")

    source_head = _sample_hashes(source, source_table, descending=False)
    target_head = _sample_hashes(target, TARGET_TABLE, descending=False)
    source_tail = _sample_hashes(source, source_table, descending=True)
    target_tail = _sample_hashes(target, TARGET_TABLE, descending=True)
    if source_head != target_head or source_tail != target_tail:
        failures.append("sampled vector hashes differ")

    source_neighbors = _neighbors(source, source_table)
    target_neighbors = _neighbors(target, TARGET_TABLE)
    if source_neighbors != target_neighbors:
        failures.append("neighbor samples differ")
    else:
        for tmdb_id, title, distance in target_neighbors:
            print(f"neighbor: {tmdb_id} {title} distance={distance}")

    if failures:
        raise SystemExit("verification failed: " + "; ".join(failures))
    print("verification passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy the movie catalog and embeddings into the new schema.")
    parser.add_argument("--source-db", default=SOURCE_DATABASE)
    parser.add_argument("--target-db", default=TARGET_DATABASE)
    parser.add_argument("--source-table", default=SOURCE_TABLE)
    parser.add_argument("--truncate", action="store_true", help="Clear the target movies table before copying.")
    args = parser.parse_args()

    settings = Settings()
    if args.source_db == args.target_db:
        raise SystemExit("Source and target databases must differ")
    if args.target_db in {"watchlog_db", "watchlog_test"}:
        raise SystemExit(f"Refusing to copy movies into {args.target_db}")

    source_url = _database_url(settings, args.source_db)
    target_url = _database_url(settings, args.target_db)

    with psycopg.connect(source_url) as source, psycopg.connect(target_url) as target:
        if args.truncate:
            target.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(_table(TARGET_TABLE)))
            target.commit()
        else:
            existing, _ = _counts(target, TARGET_TABLE)
            if existing:
                raise SystemExit(f"{args.target_db}.{TARGET_TABLE} already has {existing} rows; pass --truncate")

        print(f"copying {args.source_db}.{args.source_table} -> {args.target_db}.{TARGET_TABLE}")
        _copy(source, target, args.source_table)
        target.execute(
            sql.SQL(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {}"
            ).format(_table(TARGET_TABLE)),
            ("public.movies",),
        )
        target.execute(sql.SQL("ANALYZE {}").format(_table(TARGET_TABLE)))
        target.commit()

        _verify(source, target, args.source_table)


if __name__ == "__main__":
    main()
