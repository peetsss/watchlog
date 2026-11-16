import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.movie import Movie
from app.services.embeddings import (
    EMBED_DIMENSIONS,
    backfill_embeddings,
    build_movie_document,
    clean_names,
    format_query_for_embedding,
    normalize_text,
    request_embeddings,
    request_query_vector,
    truncate_text,
    validate_dimensions,
)


def make_movie(**kwargs: object) -> Movie:
    values: dict[str, object] = {"title": "Movie"}
    values.update(kwargs)
    return Movie(**values)


def fake_vector(value: float = 0.5) -> list[float]:
    return [value] * EMBED_DIMENSIONS


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self.payload


class FakeClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, json: dict[str, object], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self.payload)


def test_full_movie_document() -> None:
    movie = make_movie(
        title="Dune",
        tagline="It begins.",
        description="A noble family at war.",
        genres="Science Fiction, Adventure",
        keywords="desert, space war",
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Rebecca Ferguson",
    )

    document = build_movie_document(movie)

    assert "Title: Dune" in document
    assert "Tagline: It begins." in document
    assert "Overview: A noble family at war." in document
    assert "Genres: Science Fiction, Adventure" in document
    assert "Keywords: desert, space war" in document
    assert "Directed by: Denis Villeneuve" in document
    assert "Cast: Timothée Chalamet, Rebecca Ferguson" in document


def test_sparse_movie_has_title_only() -> None:
    assert build_movie_document(make_movie(title="Dune")) == "Title: Dune"


def test_overview_is_truncated() -> None:
    document = build_movie_document(make_movie(title="Dune", description="x" * 2000))

    assert document.startswith("Title: Dune\nOverview: ")
    assert document.endswith("...")
    assert len(document) <= 2500


def test_keywords_are_capped() -> None:
    keywords = ", ".join(f"kw{index:02d}" for index in range(40))

    document = build_movie_document(make_movie(title="Dune", keywords=keywords))

    keywords_line = next(line for line in document.split("\n") if line.startswith("Keywords: "))
    assert len(keywords_line.removeprefix("Keywords: ").split(", ")) == 30


def test_whitespace_only_fields_are_skipped() -> None:
    movie = make_movie(title="Dune", description="   \n  ", tagline="")

    assert build_movie_document(movie) == "Title: Dune"


def test_normalize_text() -> None:
    assert normalize_text("a  b\nc &amp; d") == "a b c & d"
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_truncate_text() -> None:
    assert truncate_text("short", 100) == "short"
    truncated = truncate_text("word " * 100, 50)
    assert truncated.endswith("...")
    assert len(truncated) <= 50


def test_clean_names() -> None:
    assert clean_names("Action, action,  Adventure ,,") == ["Action", "Adventure"]
    assert clean_names(None) == []
    assert clean_names("a, b, c, d", limit=2) == ["a", "b"]


def test_format_query_for_embedding() -> None:
    wrapped = format_query_for_embedding("space opera")

    assert wrapped.startswith("Instruct: ")
    assert "\nQuery:space opera" in wrapped


def test_empty_query_raises() -> None:
    with pytest.raises(ValueError):
        format_query_for_embedding("   ")


def test_validate_dimensions() -> None:
    validate_dimensions([0.1] * EMBED_DIMENSIONS)
    with pytest.raises(ValueError):
        validate_dimensions([0.1] * 10)


def test_request_embeddings_success() -> None:
    client = FakeClient({"embeddings": [fake_vector(0.1), fake_vector(0.2)]})

    vectors = request_embeddings(client, ["a", "b"], dimensions=EMBED_DIMENSIONS)

    assert len(vectors) == 2
    assert vectors[0] == fake_vector(0.1)
    assert client.calls[0]["json"]["dimensions"] == EMBED_DIMENSIONS
    assert len(client.calls[0]["json"]["input"]) == 2


def test_request_embeddings_empty_texts_skip_request() -> None:
    client = FakeClient({})

    assert request_embeddings(client, []) == []
    assert client.calls == []


def test_request_embeddings_missing_key_raises() -> None:
    client = FakeClient({"oops": []})

    with pytest.raises(ValueError):
        request_embeddings(client, ["a"])


def test_request_embeddings_count_mismatch_raises() -> None:
    client = FakeClient({"embeddings": [fake_vector()]})

    with pytest.raises(ValueError):
        request_embeddings(client, ["a", "b"])


def test_request_embeddings_dimension_mismatch_raises() -> None:
    client = FakeClient({"embeddings": [[0.1, 0.2]]})

    with pytest.raises(ValueError):
        request_embeddings(client, ["a"])


def test_request_query_vector() -> None:
    client = FakeClient({"embeddings": [fake_vector(0.3)]})

    vector = request_query_vector(client, "space opera")

    assert vector == fake_vector(0.3)
    assert "Instruct: " in client.calls[0]["json"]["input"][0]


def test_backfill_embeds_unembedded_movies(sync_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sync_session.add_all(
        [
            Movie(tmdb_id=1, title="One", description="First movie"),
            Movie(tmdb_id=2, title="Two", description="Second movie"),
            Movie(tmdb_id=3, title="Three"),
        ]
    )
    sync_session.commit()

    def fake_request(client: FakeClient, texts: list[str], *args: object, **kwargs: object) -> list[list[float]]:
        return [fake_vector(index) for index, _ in enumerate(texts)]

    monkeypatch.setattr("app.services.embeddings.request_embeddings", fake_request)

    stats = backfill_embeddings(sync_session, FakeClient({}))

    assert stats == {"processed": 3, "embedded": 3}
    assert sync_session.scalars(select(Movie).where(Movie.embeddings.is_(None))).all() == []
    movie = sync_session.scalars(select(Movie).where(Movie.tmdb_id == 1)).one()
    assert len(movie.embeddings) == EMBED_DIMENSIONS


def test_backfill_skips_embedded_movies(sync_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    embedded = Movie(tmdb_id=2, title="Two", embeddings=fake_vector())
    sync_session.add_all([Movie(tmdb_id=1, title="One"), embedded])
    sync_session.commit()

    def fake_request(client: FakeClient, texts: list[str], *args: object, **kwargs: object) -> list[list[float]]:
        return [fake_vector(index) for index, _ in enumerate(texts)]

    monkeypatch.setattr("app.services.embeddings.request_embeddings", fake_request)

    stats = backfill_embeddings(sync_session, FakeClient({}))

    assert stats == {"processed": 1, "embedded": 1}


def test_backfill_honors_the_limit(sync_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sync_session.add_all([Movie(tmdb_id=index, title=f"Movie {index}") for index in range(1, 4)])
    sync_session.commit()

    def fake_request(client: FakeClient, texts: list[str], *args: object, **kwargs: object) -> list[list[float]]:
        return [fake_vector(index) for index, _ in enumerate(texts)]

    monkeypatch.setattr("app.services.embeddings.request_embeddings", fake_request)

    stats = backfill_embeddings(sync_session, FakeClient({}), limit=2)

    assert stats == {"processed": 2, "embedded": 2}
    assert len(sync_session.scalars(select(Movie).where(Movie.embeddings.is_(None))).all()) == 1


def test_backfill_rejects_dimension_mismatch(sync_session: Session) -> None:
    with pytest.raises(ValueError):
        backfill_embeddings(sync_session, FakeClient({}), dimensions=4096)


def test_backfill_rejects_invalid_batch_size(sync_session: Session) -> None:
    with pytest.raises(ValueError):
        backfill_embeddings(sync_session, FakeClient({}), batch_size=0)
