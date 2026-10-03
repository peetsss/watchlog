from django.conf import settings
from django.db import models
from django.db.models import Q
from pgvector.django import HnswIndex, VectorField


class Movie(models.Model):
    class MediaType(models.TextChoices):
        MOVIE = "movie"
        SERIES = "series"

    tmdb_id = models.IntegerField(unique=True, null=True, blank=True)
    imdb_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    title = models.TextField()
    original_title = models.TextField(null=True, blank=True)
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.MOVIE)
    description = models.TextField(null=True, blank=True)
    tagline = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)
    adult = models.BooleanField(default=False)
    genres = models.TextField(null=True, blank=True)
    keywords = models.TextField(null=True, blank=True)
    director = models.TextField(null=True, blank=True)
    writers = models.TextField(null=True, blank=True)
    actors = models.TextField(null=True, blank=True)
    country = models.TextField(null=True, blank=True)
    original_language = models.CharField(max_length=10, null=True, blank=True)
    spoken_languages = models.TextField(null=True, blank=True)
    production_companies = models.TextField(null=True, blank=True)
    poster_path = models.CharField(max_length=255, null=True, blank=True)
    backdrop_path = models.CharField(max_length=255, null=True, blank=True)
    awards = models.TextField(null=True, blank=True)
    revenue = models.BigIntegerField(null=True, blank=True)
    budget = models.BigIntegerField(null=True, blank=True)
    tmdb_score = models.FloatField(null=True, blank=True)
    vote_count = models.IntegerField(null=True, blank=True)
    popularity = models.FloatField(null=True, blank=True)
    imdb_score = models.FloatField(null=True, blank=True)
    rottentomato_score = models.CharField(max_length=10, null=True, blank=True)
    metacritic_score = models.CharField(max_length=10, null=True, blank=True)
    filmweb_score = models.FloatField(null=True, blank=True)
    imdb_url = models.URLField(null=True, blank=True)
    rottentomato_url = models.URLField(null=True, blank=True)
    metacritic_url = models.URLField(null=True, blank=True)
    filmweb_url = models.URLField(null=True, blank=True)
    homepage = models.TextField(null=True, blank=True)
    embeddings = VectorField(dimensions=1024, null=True, blank=True)

    def __str__(self) -> str:
        return str(self.title)

    class Meta:
        indexes = [
            HnswIndex(
                name="movie_embeddings_hnsw_idx",
                fields=["embeddings"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]


class UserMovieLibrary(models.Model):
    """One row per (user, movie); personal scope, never exposed to other users.

    `watchlist_added_at` non-null means currently in personal Want-to-watch.
    `first_watched_at` non-null means the user has watched it.
    The two timestamps are independent: re-adding a watched movie leaves
    both populated.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="movie_library")
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="library_entries")
    watchlist_added_at = models.DateTimeField(null=True, blank=True)
    first_watched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Keep DB-free: may run in async contexts under ASGI.
    def __str__(self) -> str:
        return f"user {self.user_id} - movie {self.movie_id}"

    @property
    def in_watchlist(self) -> bool:
        return self.watchlist_added_at is not None

    @property
    def watched(self) -> bool:
        return self.first_watched_at is not None

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "movie"], name="unique_user_movie_library"),
            models.CheckConstraint(
                condition=Q(watchlist_added_at__isnull=False) | Q(first_watched_at__isnull=False),
                name="library_requires_state",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "watchlist_added_at"]),
            models.Index(fields=["user", "first_watched_at"]),
        ]
