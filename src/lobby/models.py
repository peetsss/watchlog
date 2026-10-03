import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from groups.models import Group
from movies.models import Movie

from . import rules


class LobbySession(models.Model):
    """One simultaneous movie-choice run for a group."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ACTIVE = "active", "Active"
        MATCHED = "matched", "Matched"
        EXHAUSTED = "exhausted", "Exhausted"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="lobby_sessions")
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_lobbies")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.WAITING)
    rules_version = models.CharField(max_length=20, default=rules.RULES_VERSION)
    quiz_version = models.CharField(max_length=20, default=rules.QUIZ_VERSION)
    quiz_snapshot = models.JSONField(default=dict)
    resolved_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Lobby {self.id} ({self.group.name}, {self.status})"

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.WAITING, self.Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group"],
                condition=Q(status__in=["waiting", "active"]),
                name="unique_open_lobby_per_group",
            ),
        ]
        indexes = [models.Index(fields=["group", "status"])]


class LobbyParticipant(models.Model):
    """Frozen roster entry; quiz answers are session-scoped, never global."""

    class State(models.TextChoices):
        JOINED = "joined", "Joined"
        ACTIVE = "active", "Active"

    session = models.ForeignKey(LobbySession, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lobby_participations")
    state = models.CharField(max_length=10, choices=State.choices, default=State.JOINED)
    quiz_answers = models.JSONField(default=dict)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user} in {self.session_id}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_lobby_participant"),
        ]


class LobbyCard(models.Model):
    """Durable record for a movie proposed in a session."""

    class Source(models.TextChoices):
        SYSTEM = "system", "System"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        CURRENT = "current", "Current"
        VETOED = "vetoed", "Vetoed"
        WATCHED = "watched", "Watched"
        MATCHED = "matched", "Matched"

    session = models.ForeignKey(LobbySession, on_delete=models.CASCADE, related_name="cards")
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT, related_name="lobby_cards")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.SYSTEM)
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="picked_cards"
    )
    position = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    pitch = models.TextField(null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.movie.title} [{self.status}] in {self.session_id}"

    @property
    def is_resolved(self) -> bool:
        return self.status in (self.Status.VETOED, self.Status.WATCHED, self.Status.MATCHED)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "movie"], name="unique_lobby_card"),
            models.UniqueConstraint(
                fields=["session"],
                condition=Q(status="current"),
                name="unique_current_card_per_session",
            ),
        ]
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["session", "status", "position"])]


class LobbyBallot(models.Model):
    """One participant's private choice on a card."""

    class Choice(models.TextChoices):
        WANT = "want", "Want to watch"
        WATCHED = "watched", "Watched it"
        NOT_INTERESTED = "not_interested", "Not interested"

    card = models.ForeignKey(LobbyCard, on_delete=models.CASCADE, related_name="ballots")
    participant = models.ForeignKey(LobbyParticipant, on_delete=models.CASCADE, related_name="ballots")
    choice = models.CharField(max_length=15, choices=Choice.choices)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.participant.user} -> {self.choice} on {self.card_id}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["card", "participant"], name="unique_ballot_per_card_participant"),
        ]


class WatchlistOffer(models.Model):
    """One offer per resolved card with >=1 Watched-it choice."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    card = models.OneToOneField(LobbyCard, on_delete=models.CASCADE, related_name="watch_offer")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Offer for {self.card_id} [{self.status}]"


class WatchlistOfferResponse(models.Model):
    """Per eligible non-watcher participant; created up-front for reconnects."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ADDED = "added", "Added to group"
        DISMISSED = "dismissed", "Dismissed"
        CLOSED = "closed", "Closed"

    offer = models.ForeignKey(WatchlistOffer, on_delete=models.CASCADE, related_name="responses")
    participant = models.ForeignKey(LobbyParticipant, on_delete=models.CASCADE, related_name="offer_responses")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.participant.user} {self.status} on {self.offer_id}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["offer", "participant"], name="unique_offer_response"),
        ]
