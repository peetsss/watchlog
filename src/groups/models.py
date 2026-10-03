import uuid

from django.conf import settings
from django.db import models

from movies.models import Movie


class Group(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="GroupMembership", related_name="movie_groups")

    # Keep DB-free: may run in async contexts under ASGI.
    def __str__(self) -> str:
        return f"{self.uuid} {self.name}"


class GroupMembership(models.Model):
    class Roles(models.TextChoices):
        ADMIN = "admin"
        MEMBER = "member"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Roles.choices, default=Roles.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "group")

    def __str__(self) -> str:
        return f"user {self.user_id} in group {self.group_id} ({self.role})"


class GroupMovie(models.Model):
    class Status(models.TextChoices):
        SUGGESTED = "Suggested"
        WATCHED = "Watched"

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT)
    average_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    suggested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="suggestions"
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SUGGESTED)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("group", "movie")
        ordering = ["-added_at"]

    def __str__(self) -> str:
        return f"group {self.group_id} - movie {self.movie_id} - {self.average_score}"


class Review(models.Model):
    group_movie = models.ForeignKey(GroupMovie, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=3, decimal_places=1)
    comment = models.TextField(blank=True)
    contains_spoilers = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("group_movie", "user")

    def __str__(self) -> str:
        return f"user {self.user_id} rated group_movie {self.group_movie_id}: {self.score}"
