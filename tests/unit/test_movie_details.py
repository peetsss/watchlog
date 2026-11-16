from datetime import date

import pytest

from app.services.movies import create_movie_from_details

MOVIE_DETAILS: dict[str, object] = {
    "id": 438631,
    "title": "Dune",
    "original_title": "Dune",
    "overview": "A noble family becomes embroiled in a war.",
    "tagline": "It begins.",
    "status": "Released",
    "runtime": 155,
    "release_date": "2021-10-22",
    "adult": False,
    "genres": [{"id": 878, "name": "Science Fiction"}, {"id": 12, "name": "Adventure"}],
    "poster_path": "/d5vxZgWJJcpLfPtHnOJmsPfUCBq.jpg",
    "backdrop_path": "/jYoe5UywHmS4xtQ7dgyLIzLuWxc.jpg",
    "vote_average": 7.8,
    "revenue": 1083300000,
    "budget": 165000000,
    "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
    "production_companies": [{"id": 1, "name": "Legendary Pictures"}],
    "spoken_languages": [{"english_name": "English", "name": "English"}],
    "original_language": "en",
    "homepage": "https://www.dunemovie.com",
    "credits": {
        "crew": [
            {"name": "Denis Villeneuve", "job": "Director"},
            {"name": "Jon Spaihts", "job": "Screenplay"},
        ],
        "cast": [{"name": "Timothée Chalamet"}, {"name": "Rebecca Ferguson"}],
    },
    "keywords": {"keywords": [{"name": "desert"}, {"name": "space war"}]},
    "external_ids": {"imdb_id": "tt11604119"},
}

SERIES_DETAILS: dict[str, object] = {
    "id": 1399,
    "name": "Game of Thrones",
    "original_name": "Game of Thrones",
    "overview": "Noble families fight for control.",
    "first_air_date": "2011-04-17",
    "episode_run_time": [57],
    "genres": [{"name": "Drama"}],
    "keywords": {"results": [{"name": "kingdom"}]},
    "external_ids": {"imdb_id": "tt0944947"},
}


def test_create_movie_from_details() -> None:
    movie = create_movie_from_details(MOVIE_DETAILS, "movie")

    assert movie.tmdb_id == 438631
    assert movie.title == "Dune"
    assert movie.media_type == "movie"
    assert movie.release_date == date(2021, 10, 22)
    assert movie.runtime == 155
    assert movie.genres == "Science Fiction, Adventure"
    assert movie.director == "Denis Villeneuve"
    assert movie.writers == "Jon Spaihts"
    assert movie.actors == "Timothée Chalamet, Rebecca Ferguson"
    assert movie.country == "United States of America"
    assert movie.keywords == "desert, space war"
    assert movie.tmdb_score == 7.8
    assert movie.poster_path == "https://image.tmdb.org/t/p/w500/d5vxZgWJJcpLfPtHnOJmsPfUCBq.jpg"
    assert movie.backdrop_path == "https://image.tmdb.org/t/p/original/jYoe5UywHmS4xtQ7dgyLIzLuWxc.jpg"
    assert movie.imdb_id == "tt11604119"
    assert movie.imdb_url == "https://www.imdb.com/title/tt11604119"
    assert movie.homepage == "https://www.dunemovie.com"


def test_create_series_from_details() -> None:
    movie = create_movie_from_details(SERIES_DETAILS, "series")

    assert movie.media_type == "series"
    assert movie.title == "Game of Thrones"
    assert movie.release_date == date(2011, 4, 17)
    assert movie.runtime == 57
    assert movie.keywords == "kingdom"


def test_invalid_media_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported media type"):
        create_movie_from_details(MOVIE_DETAILS, "podcast")


def test_missing_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="numeric id"):
        create_movie_from_details({"title": "Dune"}, "movie")
