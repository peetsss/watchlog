"""Idempotent personal-library operations.

Owner-scoped helpers for `movies.UserMovieLibrary`. All writes are atomic
and safe to retry: repeated calls with the same (user, movie) converge
without duplicating rows or clobbering existing timestamps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from .models import Movie, UserMovieLibrary

if TYPE_CHECKING:
    from user.models import User


@transaction.atomic
def add_to_personal_watchlist(user: User, movie: Movie) -> UserMovieLibrary:
    """Mark `movie` as Want-to-watch for `user`, retaining watched history."""
    entry, created = UserMovieLibrary.objects.get_or_create(
        user=user,
        movie=movie,
        defaults={"watchlist_added_at": timezone.now()},
    )
    if created:
        return entry
    if entry.watchlist_added_at is None:
        entry.watchlist_added_at = timezone.now()
        entry.save(update_fields=["watchlist_added_at", "updated_at"])
    return entry


@transaction.atomic
def mark_personally_watched(user: User, movie: Movie) -> UserMovieLibrary:
    """Record personal watch history; clear active watchlist membership.

    Keeps the original `first_watched_at` when already set.
    """
    entry, created = UserMovieLibrary.objects.get_or_create(
        user=user,
        movie=movie,
        defaults={"first_watched_at": timezone.now()},
    )
    if created:
        return entry
    updated_fields: list[str] = ["updated_at"]
    if entry.first_watched_at is None:
        entry.first_watched_at = timezone.now()
        updated_fields.append("first_watched_at")
    if entry.watchlist_added_at is not None:
        entry.watchlist_added_at = None
        updated_fields.append("watchlist_added_at")
    if len(updated_fields) > 1:
        entry.save(update_fields=updated_fields)
    return entry


@transaction.atomic
def remove_from_personal_watchlist(user: User, movie: Movie) -> None:
    """Clear watchlist membership; delete the row only if never watched."""
    try:
        entry = UserMovieLibrary.objects.get(user=user, movie=movie)
    except UserMovieLibrary.DoesNotExist:
        return
    if entry.first_watched_at is not None:
        if entry.watchlist_added_at is not None:
            entry.watchlist_added_at = None
            entry.save(update_fields=["watchlist_added_at", "updated_at"])
        return
    entry.delete()


def get_personal_watchlist(user: User):
    """Queryset of active Want-to-watch entries for `user`, newest first."""
    return (
        UserMovieLibrary.objects.filter(user=user, watchlist_added_at__isnull=False)
        .select_related("movie")
        .order_by("-watchlist_added_at")
    )


def get_personal_history(user: User):
    """Queryset of watched entries for `user`, newest first."""
    return (
        UserMovieLibrary.objects.filter(user=user, first_watched_at__isnull=False)
        .select_related("movie")
        .order_by("-first_watched_at")
    )
