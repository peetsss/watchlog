from django.db import models


class Movie(models.Model):
    class MovieType(models.TextChoices):
        MOVIE = "movie"
        SERIES = "series"

    imdb_id = models.CharField(max_length=255, primary_key=True, unique=True)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=MovieType.choices)
    description = models.TextField()
    year = models.DateField()
    genre = models.TextField()
    director = models.TextField()
    writers = models.TextField()
    actors = models.TextField()
    country = models.TextField()
    poster = models.CharField(max_length=255)
    awards = models.TextField()
    imdb_score = models.CharField(max_length=10)
    rottentomato_score = models.CharField(max_length=10)
    metacritic_score = models.CharField(max_length=10)
    filmweb_score = models.CharField(max_length=10, null=True, blank=True)
    imdb_url = models.TextField()
    rottentomato_url = models.TextField()
    metacritic_url = models.TextField()
    filmweb_url = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return str(self.title)
