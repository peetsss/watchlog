"""Ollama pitch provider with deterministic fallback.

Pitch failure must never prevent voting: every entry point returns a usable
string and never raises for network/model errors. Timeouts are bounded and
all network calls are mockable in tests.
"""

from __future__ import annotations

import os
from typing import Any

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://100.99.131.45:11434")
PITCH_MODEL = os.getenv("OLLAMA_PITCH_MODEL", "qwen3:latest")
PITCH_TIMEOUT = float(os.getenv("OLLAMA_PITCH_TIMEOUT", "10"))


def fallback_pitch(movie, intent_text: str | None = None) -> str:
    """Deterministic title/genre-based pitch; always available."""
    title = getattr(movie, "title", "This pick")
    genres = (getattr(movie, "genres", None) or "").strip()
    year = ""
    release_date = getattr(movie, "release_date", None)
    if release_date:
        try:
            year = f" ({release_date.year})"
        except AttributeError:
            year = ""
    base = f"{title}{year}"
    if genres:
        base += f" — {genres}"
    else:
        base += " — a crowd-pleasing pick"
    if intent_text:
        cleaned = " ".join(intent_text.split())
        if cleaned:
            return f"{base}. Fits tonight: {cleaned}"
    return f"{base}."


def build_pitch_prompt(movie, intent_text: str | None = None) -> str:
    """Prompt for the Ollama chat/generate endpoint (pure, testable)."""
    title = getattr(movie, "title", "Unknown")
    genres = getattr(movie, "genres", None) or "unknown genres"
    description = (getattr(movie, "description", None) or "")[:500]
    mood = intent_text or "a fun group movie night"
    return (
        "Write a one-sentence, spoiler-free movie-night pitch. "
        f"Movie: {title} ({genres}). Overview: {description}. Mood: {mood}."
    )


def request_pitch_text(
    movie,
    intent_text: str | None = None,
    *,
    client: Any | None = None,
    model: str = PITCH_MODEL,
    ollama_url: str = OLLAMA_URL,
    timeout: float = PITCH_TIMEOUT,
) -> str | None:
    """Ask Ollama for a pitch; None on any failure (caller falls back)."""
    prompt = build_pitch_prompt(movie, intent_text)
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        if client is None:
            import httpx

            with httpx.Client(timeout=timeout) as own:
                response = own.post(f"{ollama_url}/api/generate", json=payload, timeout=timeout)
        else:
            response = client.post(f"{ollama_url}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    text = (data.get("response") or data.get("text") or "").strip()
    return text or None


def get_pitch(
    movie,
    intent_text: str | None = None,
    *,
    client: Any | None = None,
    **kwargs: Any,
) -> str:
    """Best-effort pitch with guaranteed fallback; never raises."""
    try:
        text = request_pitch_text(movie, intent_text, client=client, **kwargs)
    except Exception:
        text = None
    return text if text else fallback_pitch(movie, intent_text)


def ensure_card_pitch(card, intent_text: str | None = None, *, client: Any | None = None, **kwargs) -> str:
    """Fill `card.pitch` when empty; returns the pitch. Never blocks voting."""
    existing = getattr(card, "pitch", None)
    if existing:
        return existing
    pitch = get_pitch(card.movie, intent_text, client=client, **kwargs)
    try:
        card.pitch = pitch
        card.save(update_fields=["pitch"])
    except Exception:
        pass
    return pitch
