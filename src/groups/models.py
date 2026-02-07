import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from movies.models import Movie


class Group(models.Model):
    code = models.CharField(
        primary_key=True,
        max_length=10,
        unique=True,
        editable=False,
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="GroupMembership",
        related_name="group_memberships",
    )

    def save(self, *args, **kwargs) -> None:
        if not self.pk:
            self.generate_unique_code()
        original_slug = slugify(self.name)
        self.slug = original_slug
        if Group.objects.filter(slug=self.slug).exists():
            self.slug = f"{original_slug}-{uuid.uuid4().hex[:2]}"
        super().save(*args, **kwargs)

    def generate_unique_code(self) -> None:
        while True:
            self.code = uuid.uuid4().hex[:10]
            if not Group.objects.filter(code=self.code).exists():
                break

    def __str__(self) -> str:
        member_names = ", ".join([member.username for member in self.members.all()])
        return f"{self.name} {self.slug}: {member_names} - {self.code}"


class GroupMembership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.group.name}"


class GroupMovie(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    average_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    watched = models.BooleanField(default=False)
    added_by = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        unique_together = ("group", "movie")

    def __str__(self) -> str:
        return f"{self.group.name} - {self.movie.title} - {self.average_score}"


class UserScore(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=3, decimal_places=1)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "movie", "group")

    def __str__(self) -> str:
        return f"{self.user.username} - {self.movie.title} - {self.group} - {self.score}"
