import pytest

from scripts.ingest_tmdb import MovieRow

ROW = {
    "id": "438631",
    "title": "Dune",
    "vote_average": "7.8",
    "vote_count": "1000",
    "status": "Released",
    "release_date": "2021-10-22",
    "revenue": "100",
    "runtime": "155",
    "adult": "False",
    "backdrop_path": "/backdrop.jpg",
    "budget": "50",
    "imdb_id": "tt11604119",
    "original_title": "Dune",
    "overview": "A noble family becomes embroiled in a war.",
    "popularity": "10.0",
    "poster_path": "/poster.jpg",
    "tagline": "It begins.",
    "homepage": "https://www.dunemovie.com",
    "original_language": "en",
    "genres": "Science Fiction, Adventure",
    "production_companies": "Legendary Pictures",
    "production_countries": "United States of America",
    "spoken_languages": "English",
    "keywords": "desert, space war",
}


def test_parse_and_map_a_movie_row() -> None:
    parsed = MovieRow.from_row(ROW, min_votes=10)

    assert parsed is not None
    assert parsed.tmdb_id == 438631
    assert parsed.title == "Dune"
    assert parsed.vote_count == 1000
    assert parsed.genres == ["Science Fiction", "Adventure"]
    assert parsed.production_countries == ["United States of America"]

    movie = parsed.to_model()

    assert movie.tmdb_id == 438631
    assert movie.title == "Dune"
    assert movie.media_type == "movie"
    assert movie.status == "Released"
    assert movie.runtime == 155
    assert movie.genres == "Science Fiction, Adventure"
    assert movie.keywords == "desert, space war"
    assert movie.country == "United States of America"
    assert movie.imdb_id == "tt11604119"
    assert movie.poster_path == "https://image.tmdb.org/t/p/w500/poster.jpg"
    assert movie.backdrop_path == "https://image.tmdb.org/t/p/original/backdrop.jpg"
    assert movie.imdb_url == "https://www.imdb.com/title/tt11604119"


def test_filtering_rules() -> None:
    assert MovieRow.from_row({**ROW, "status": "Post Production"}) is None
    assert MovieRow.from_row({**ROW, "overview": ""}) is None
    assert MovieRow.from_row({**ROW, "vote_count": "5"}, min_votes=10) is None


def test_missing_title_is_malformed() -> None:
    with pytest.raises(ValueError):
        MovieRow.from_row({**ROW, "title": ""})


def test_zero_imdb_id_is_treated_as_missing() -> None:
    parsed = MovieRow.from_row({**ROW, "imdb_id": "0"})

    assert parsed is not None
    assert parsed.imdb_id is None


def test_invalid_release_date_is_ignored() -> None:
    parsed = MovieRow.from_row({**ROW, "release_date": "not-a-date"})

    assert parsed is not None
    assert parsed.release_date is None
