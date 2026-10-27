import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from groups.models import Group
from lobby import rules
from movies.models import Movie


class Lobby(models.Model):
    class Type(models.TextChoices):
        GROUP = rules.GROUP_LOBBY, "Group"
        OPEN = rules.OPEN_LOBBY, "Open"

    class Status(models.TextChoices):
        READY = rules.READY, "Ready"
        PLAYING = rules.PLAYING, "Playing"
        FINAL_ROUND = rules.FINAL_ROUND, "Final Round"
        FINISHED = rules.FINISHED, "Finished"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="lobbies",
    )
    type = models.CharField(max_length=8, choices=Type.choices, default=Type.OPEN)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosted_lobbies",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.READY)
    pool = models.JSONField(default=list)
    pool_index = models.PositiveIntegerField(default=0)  # type: ignore[argument]
    ready = models.JSONField(default=list)
    votes = models.JSONField(default=dict)
    picks = models.JSONField(default=dict)
    finalists = models.JSONField(default=list, null=True, blank=True)
    winner_movie = models.ForeignKey(
        Movie,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lobby_winners",
    )
    version = models.IntegerField(default=0)  # type: ignore[argument]
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(type=rules.GROUP_LOBBY, group__isnull=False) | Q(type=rules.OPEN_LOBBY, group__isnull=True),
                name="lobby_group_matches_type",
            ),
            models.UniqueConstraint(
                fields=["group"],
                condition=Q(status__in=[rules.READY, rules.PLAYING, rules.FINAL_ROUND]),
                name="unique_active_lobby_per_group",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="idx_lobby_status"),
            models.Index(fields=["group", "status"], name="idx_lobby_group_status"),
        ]

    def __str__(self) -> str:
        return f"Lobby {self.uuid} ({self.type} / {self.status})"


class LobbyMembership(models.Model):
    class Roles(models.TextChoices):
        HOST = rules.HOST_ROLE, "Host"
        MEMBER = rules.MEMBER_ROLE, "Member"

    lobby = models.ForeignKey(Lobby, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lobby_memberships",
    )
    role = models.CharField(max_length=8, choices=Roles.choices, default=Roles.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("lobby", "user")
        constraints = [
            models.UniqueConstraint(
                fields=["lobby"],
                condition=Q(role=rules.HOST_ROLE),
                name="unique_host_membership_per_lobby",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.lobby.uuid}"  # type: ignore[attr-defined]
