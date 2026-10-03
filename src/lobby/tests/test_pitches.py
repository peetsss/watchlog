from datetime import date

from django.test import SimpleTestCase

from lobby import pitches
from lobby.pitches import build_pitch_prompt, ensure_card_pitch, fallback_pitch, get_pitch


class FakeMovie:
    def __init__(self, **kwargs):
        self.title = kwargs.get("title", "Dune")
        self.genres = kwargs.get("genres", "Science Fiction, Adventure")
        self.description = kwargs.get("description", "Desert epic.")
        self.release_date = kwargs.get("release_date", date(2021, 10, 22))


class FakeResponse:
    def __init__(self, payload=None, raise_error=None):
        self.payload = payload or {}
        self.raise_error = raise_error

    def raise_for_status(self):
        if self.raise_error:
            raise self.raise_error

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.response


class FakeCard:
    def __init__(self, movie, pitch=None):
        self.movie = movie
        self.pitch = pitch
        self.saved = False

    def save(self, update_fields=None):
        self.saved = True


class FallbackPitchTests(SimpleTestCase):
    def test_includes_title_genres_and_mood(self):
        text = fallback_pitch(FakeMovie(), "something light and cozy")
        self.assertIn("Dune", text)
        self.assertIn("Science Fiction", text)
        self.assertIn("something light and cozy", text)

    def test_works_without_genres_or_mood(self):
        text = fallback_pitch(FakeMovie(genres=None, release_date=None))
        self.assertIn("Dune", text)
        self.assertTrue(text.endswith("."))
        self.assertEqual(fallback_pitch(FakeMovie(genres=""), None), "Dune (2021) — a crowd-pleasing pick.")

    def test_prompt_is_deterministic(self):
        self.assertEqual(build_pitch_prompt(FakeMovie()), build_pitch_prompt(FakeMovie()))


class OllamaPitchTests(SimpleTestCase):
    def test_success_returns_ollama_text(self):
        client = FakeClient(FakeResponse({"response": "  A roaring night. "}))
        text = get_pitch(FakeMovie(), "cozy", client=client, timeout=5)
        self.assertEqual(text, "A roaring night.")
        self.assertIn("/api/generate", client.calls[0]["url"])
        self.assertEqual(client.calls[0]["timeout"], 5)
        self.assertFalse(client.calls[0]["json"]["stream"])

    def test_failure_falls_back_without_raising(self):
        client = FakeClient(FakeResponse({}, raise_error=Exception("boom")))
        text = get_pitch(FakeMovie(), client=client)
        self.assertIn("Dune", text)

    def test_empty_response_falls_back(self):
        client = FakeClient(FakeResponse({"response": "   "}))
        self.assertIn("Dune", get_pitch(FakeMovie(), client=client))

    def test_ensure_card_pitch_fills_and_keeps_existing(self):
        card = FakeCard(FakeMovie())
        pitch = ensure_card_pitch(card, "cozy", client=FakeClient(FakeResponse({"response": " Epic. "})))
        self.assertEqual(pitch, "Epic.")
        self.assertEqual(card.pitch, "Epic.")
        self.assertTrue(card.saved)

        card2 = FakeCard(FakeMovie(), pitch="Kept")
        self.assertEqual(ensure_card_pitch(card2, client=FakeClient(FakeResponse({"response": "New"}))), "Kept")

    def test_voting_never_blocked_by_pitch_errors(self):
        class ExplodingClient:
            def post(self, *args, **kwargs):
                raise TimeoutError("slow ollama")

        # Must return fallback, not raise.
        self.assertIn("Dune", get_pitch(FakeMovie(), client=ExplodingClient(), timeout=0.01))

    def test_module_defaults_are_bounded(self):
        self.assertLessEqual(pitches.PITCH_TIMEOUT, 30)
        self.assertTrue(pitches.PITCH_MODEL)
