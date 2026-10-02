from unittest.mock import patch

from django.test import TestCase

from movies.models import Movie
from movies.utils.embeddings import (
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


def make_movie(tmdb_id, **kwargs):
    defaults = {"title": f"Movie {tmdb_id}"}
    defaults.update(kwargs)
    return Movie.objects.create(tmdb_id=tmdb_id, **defaults)


def fake_vector(value=0.5):
    return [value] * EMBED_DIMENSIONS


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self.payload)


class DocumentBuilderTests(TestCase):
    def test_full_movie(self):
        movie = make_movie(
            1,
            title="Dune",
            tagline="It begins.",
            description="A noble family at war.",
            genres="Science Fiction, Adventure",
            keywords="desert, space war",
            director="Denis Villeneuve",
            actors="Timothée Chalamet, Rebecca Ferguson",
        )
        document = build_movie_document(movie)
        self.assertIn("Title: Dune", document)
        self.assertIn("Tagline: It begins.", document)
        self.assertIn("Overview: A noble family at war.", document)
        self.assertIn("Genres: Science Fiction, Adventure", document)
        self.assertIn("Keywords: desert, space war", document)
        self.assertIn("Directed by: Denis Villeneuve", document)
        self.assertIn("Cast: Timothée Chalamet, Rebecca Ferguson", document)

    def test_sparse_movie_has_title_only(self):
        movie = make_movie(1, title="Dune")
        self.assertEqual(build_movie_document(movie), "Title: Dune")

    def test_overview_truncated(self):
        movie = make_movie(1, title="Dune", description="x" * 2000)
        document = build_movie_document(movie)
        self.assertTrue(document.startswith("Title: Dune\nOverview: "))
        self.assertTrue(document.endswith("..."))
        self.assertLessEqual(len(document), 2500)

    def test_keywords_capped(self):
        keywords = ", ".join(f"kw{i:02d}" for i in range(40))
        movie = make_movie(1, title="Dune", keywords=keywords)
        document = build_movie_document(movie)
        keywords_line = [line for line in document.split("\n") if line.startswith("Keywords: ")][0]
        self.assertEqual(len(keywords_line.removeprefix("Keywords: ").split(", ")), 30)

    def test_whitespace_only_fields_skipped(self):
        movie = make_movie(1, title="Dune", description="   \n  ", tagline="")
        self.assertEqual(build_movie_document(movie), "Title: Dune")


class TextHelperTests(TestCase):
    def test_normalize_text(self):
        self.assertEqual(normalize_text("a  b\nc &amp; d"), "a b c & d")
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text(""), "")

    def test_truncate_text(self):
        self.assertEqual(truncate_text("short", 100), "short")
        truncated = truncate_text("word " * 100, 50)
        self.assertTrue(truncated.endswith("..."))
        self.assertLessEqual(len(truncated), 50)

    def test_clean_names(self):
        self.assertEqual(clean_names("Action, action,  Adventure ,,"), ["Action", "Adventure"])
        self.assertEqual(clean_names(None), [])
        self.assertEqual(clean_names("a, b, c, d", limit=2), ["a", "b"])


class QueryWrapperTests(TestCase):
    def test_format_query(self):
        wrapped = format_query_for_embedding("space opera")
        self.assertTrue(wrapped.startswith("Instruct: "))
        self.assertIn("\nQuery:space opera", wrapped)

    def test_empty_query_raises(self):
        with self.assertRaises(ValueError):
            format_query_for_embedding("   ")

    def test_validate_dimensions(self):
        validate_dimensions([0.1] * EMBED_DIMENSIONS)
        with self.assertRaises(ValueError):
            validate_dimensions([0.1] * 10)


class RequestEmbeddingsTests(TestCase):
    def test_success(self):
        client = FakeClient({"embeddings": [fake_vector(0.1), fake_vector(0.2)]})
        vectors = request_embeddings(client, ["a", "b"], dimensions=EMBED_DIMENSIONS)
        self.assertEqual(len(vectors), 2)
        self.assertEqual(vectors[0], fake_vector(0.1))
        self.assertEqual(client.calls[0]["json"]["dimensions"], EMBED_DIMENSIONS)
        self.assertEqual(len(client.calls[0]["json"]["input"]), 2)

    def test_empty_texts_skips_request(self):
        client = FakeClient({})
        self.assertEqual(request_embeddings(client, []), [])
        self.assertEqual(client.calls, [])

    def test_missing_key_raises(self):
        client = FakeClient({"oops": []})
        with self.assertRaises(ValueError):
            request_embeddings(client, ["a"])

    def test_count_mismatch_raises(self):
        client = FakeClient({"embeddings": [fake_vector()]})
        with self.assertRaises(ValueError):
            request_embeddings(client, ["a", "b"])

    def test_dimension_mismatch_raises(self):
        client = FakeClient({"embeddings": [[0.1, 0.2]]})
        with self.assertRaises(ValueError):
            request_embeddings(client, ["a"])

    def test_request_query_vector(self):
        client = FakeClient({"embeddings": [fake_vector(0.3)]})
        vector = request_query_vector(client, "space opera")
        self.assertEqual(vector, fake_vector(0.3))
        self.assertIn("Instruct: ", client.calls[0]["json"]["input"][0])


class BackfillTests(TestCase):
    def run_backfill(self, **kwargs):
        client = FakeClient({})
        with patch(
            "movies.utils.embeddings.request_embeddings",
            side_effect=lambda client, texts, *args, **kwargs: [fake_vector(i) for i, _ in enumerate(texts)],
        ):
            return backfill_embeddings(client, **kwargs)

    def test_embeds_all_unembedded(self):
        make_movie(1, title="One", description="First movie")
        make_movie(2, title="Two", description="Second movie")
        make_movie(3, title="Three")
        stats = self.run_backfill()
        self.assertEqual(stats, {"processed": 3, "embedded": 3})
        self.assertEqual(Movie.objects.filter(embeddings__isnull=True).count(), 0)
        movie = Movie.objects.get(tmdb_id=1)
        self.assertEqual(len(movie.embeddings), EMBED_DIMENSIONS)

    def test_skips_already_embedded(self):
        make_movie(1, title="One")
        embedded = make_movie(2, title="Two")
        embedded.embeddings = fake_vector()
        embedded.save(update_fields=["embeddings"])
        stats = self.run_backfill()
        self.assertEqual(stats, {"processed": 1, "embedded": 1})

    def test_limit(self):
        make_movie(1, title="One")
        make_movie(2, title="Two")
        make_movie(3, title="Three")
        stats = self.run_backfill(limit=2)
        self.assertEqual(stats, {"processed": 2, "embedded": 2})
        self.assertEqual(Movie.objects.filter(embeddings__isnull=True).count(), 1)

    def test_dimensions_mismatch_raises(self):
        with self.assertRaises(ValueError):
            self.run_backfill(dimensions=4096)

    def test_invalid_batch_size_raises(self):
        with self.assertRaises(ValueError):
            self.run_backfill(batch_size=0)
