from django.db import models
from pgvector.django import HnswIndex, VectorField


class Movie(models.Model):
    class MediaType(models.TextChoices):
        MOVIE = "movie"
        SERIES = "series"

    tmdb_id = models.IntegerField(unique=True, null=True, blank=True)
    imdb_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    original_title = models.CharField(max_length=255, null=True, blank=True)
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
    homepage = models.URLField(null=True, blank=True)
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
