import html
import re

import httpx

OLLAMA_URL = "http://100.99.131.45:11434"
EMBED_MODEL = "qwen3-embedding:latest"
EMBED_DIMENSIONS = 1024

MAX_OVERVIEW_CHARS = 1500
MAX_KEYWORDS = 30
MAX_CAST = 8
MAX_DOC_CHARS = 2500

DEFAULT_QUERY_TASK = "Given a movie search query, retrieve relevant movies that match the query"


def normalize_text(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars or max_chars <= 3:
        return text[:max_chars]
    prefix = text[: max_chars - 3]
    last_space = prefix.rfind(" ")
    if last_space > 0:
        prefix = prefix[:last_space]
    truncated = prefix.rstrip()
    if not truncated:
        return text[:max_chars]
    return truncated + "..."


def clean_names(value: str | None, limit: int | None = None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for chunk in (value or "").split(","):
        item = chunk.strip()
        if not item or item.lower() in seen:
            continue
        seen.add(item.lower())
        items.append(item)
        if limit is not None and len(items) >= limit:
            break
    return items


def build_movie_document(movie) -> str:
    title = normalize_text(movie.title)
    tagline = normalize_text(movie.tagline)
    overview = truncate_text(normalize_text(movie.description), MAX_OVERVIEW_CHARS)
    genres = clean_names(movie.genres)
    keywords = clean_names(movie.keywords, limit=MAX_KEYWORDS)
    director = normalize_text(movie.director)
    cast = clean_names(movie.actors, limit=MAX_CAST)

    parts = [f"Title: {title}"]
    if tagline:
        parts.append(f"Tagline: {tagline}")
    if overview:
        parts.append(f"Overview: {overview}")
    if genres:
        parts.append(f"Genres: {', '.join(genres)}")
    if keywords:
        parts.append(f"Keywords: {', '.join(keywords)}")
    credits = []
    if director:
        credits.append(f"Directed by: {director}")
    if cast:
        credits.append(f"Cast: {', '.join(cast)}")
    if credits:
        parts.append(" | ".join(credits))

    document = "\n".join(parts)
    if len(document) > MAX_DOC_CHARS:
        overflow = len(document) - MAX_DOC_CHARS
        shorter_overview = truncate_text(overview, max(len(overview) - overflow, 0))
        parts = [p for p in parts if not p.startswith("Overview: ")]
        if shorter_overview:
            parts.append(f"Overview: {shorter_overview}")
        document = "\n".join(parts)
    return document


def format_query_for_embedding(query: str, task: str = DEFAULT_QUERY_TASK) -> str:
    cleaned_query = normalize_text(query)
    if not cleaned_query:
        raise ValueError("query must not be empty")
    cleaned_task = normalize_text(task)
    if not cleaned_task:
        raise ValueError("task must not be empty")
    return f"Instruct: {cleaned_task}\nQuery:{cleaned_query}"


def validate_dimensions(vector: list[float], expected: int = EMBED_DIMENSIONS) -> None:
    if len(vector) != expected:
        raise ValueError(f"Embedding dimension mismatch: expected {expected}, got {len(vector)}")


def request_embeddings(
    client: httpx.Client,
    texts: list[str],
    model: str = EMBED_MODEL,
    ollama_url: str = OLLAMA_URL,
    dimensions: int = EMBED_DIMENSIONS,
    timeout: float = 600.0,
) -> list[list[float]]:
    if not texts:
        return []
    response = client.post(
        f"{ollama_url}/api/embed",
        json={"model": model, "input": texts, "dimensions": dimensions},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "embeddings" not in payload:
        raise ValueError(f"Ollama response missing 'embeddings' field. Keys: {sorted(payload.keys())}")
    embeddings = payload["embeddings"]
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise ValueError(f"Embedding count mismatch: requested {len(texts)}, received {len(embeddings)}")
    validated: list[list[float]] = []
    for index, embedding in enumerate(embeddings):
        if not isinstance(embedding, list):
            raise TypeError(f"Embedding at index {index} is not a list: {type(embedding)}")
        validate_dimensions(embedding, dimensions)
        validated.append(embedding)
    return validated


def request_query_vector(
    client: httpx.Client,
    query: str,
    model: str = EMBED_MODEL,
    ollama_url: str = OLLAMA_URL,
    dimensions: int = EMBED_DIMENSIONS,
    timeout: float = 600.0,
) -> list[float]:
    wrapped = format_query_for_embedding(query)
    vectors = request_embeddings(client, [wrapped], model, ollama_url, dimensions, timeout)
    if len(vectors) != 1:
        raise ValueError(f"Expected 1 embedding, got {len(vectors)}")
    return vectors[0]


def backfill_embeddings(
    client: httpx.Client,
    ollama_url: str = OLLAMA_URL,
    model: str = EMBED_MODEL,
    dimensions: int = EMBED_DIMENSIONS,
    batch_size: int = 250,
    limit: int | None = None,
    timeout: float = 600.0,
    progress=None,
) -> dict[str, int]:
    from movies.models import Movie

    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    if dimensions != EMBED_DIMENSIONS:
        raise ValueError(f"dimensions ({dimensions}) must match the embeddings column ({EMBED_DIMENSIONS})")

    processed = embedded = 0
    while True:
        remaining = None if limit is None else limit - processed
        if remaining is not None and remaining <= 0:
            break
        chunk_size = batch_size if remaining is None else min(batch_size, remaining)
        movies = list(Movie.objects.filter(embeddings__isnull=True).order_by("tmdb_id")[:chunk_size])
        if not movies:
            break
        vectors = request_embeddings(
            client,
            [build_movie_document(movie) for movie in movies],
            model,
            ollama_url,
            dimensions,
            timeout,
        )
        for movie, vector in zip(movies, vectors, strict=True):
            movie.embeddings = vector
        Movie.objects.bulk_update(movies, ["embeddings"], batch_size=500)
        processed += len(movies)
        embedded += len(movies)
        if progress:
            progress(f"embedded {embedded} movies...")
    return {"processed": processed, "embedded": embedded}
