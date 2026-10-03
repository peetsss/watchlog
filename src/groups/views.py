import uuid

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.db.models.functions import Round
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from movies.models import Movie

from .forms import GroupForm
from .middleware import group_member_required
from .models import Group, GroupMembership, GroupMovie, Review


@login_required
def create_group(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            user = request.user
            group.members.add(user)
            return redirect("group", uuid=group.uuid)

    form = GroupForm()
    return redirect("index")


@login_required
@group_member_required
def generate_invite_link(request: HttpRequest, uuid: uuid.UUID) -> JsonResponse:
    group = get_object_or_404(Group, uuid=uuid)
    invite_link = request.build_absolute_uri(reverse("join_group_by_link", kwargs={"uuid": group.uuid}))
    return JsonResponse({"invite_link": invite_link})


@login_required
def join_group_by_link(request: HttpRequest, uuid: uuid.UUID) -> HttpResponse:
    group = get_object_or_404(Group, uuid=uuid)
    user = request.user
    if user not in group.members.all():
        group.members.add(user)
    return redirect("group", uuid=group.uuid)


@group_member_required
def group_view(request: HttpRequest, uuid: uuid.UUID) -> HttpResponse:
    group = get_object_or_404(Group, uuid=uuid)
    group_movies = GroupMovie.objects.filter(group=group)
    user_scores_queryset = Review.objects.filter(group_movie__group=group).select_related("user")

    user_scores = {}
    for score in user_scores_queryset:
        movie_id = score.group_movie.movie.pk
        if movie_id not in user_scores:
            user_scores[movie_id] = []
        user_scores[movie_id].append((score.user.username, score.score))

    watched_movies = group_movies.filter(status=GroupMovie.Status.WATCHED)
    not_watched_movies = group_movies.filter(status=GroupMovie.Status.SUGGESTED)
    all_group_movies = watched_movies | not_watched_movies

    context = {
        "group": group,
        "user_scores": user_scores,
        "all_group_movies": all_group_movies,
        "watched_movies": watched_movies,
        "not_watched_movies": not_watched_movies,
    }
    return render(request, "group.html", context)


@require_POST
@login_required
def join_group(request: HttpRequest) -> HttpResponse:
    group_uuid = request.POST.get("uuid")
    if group_uuid:
        group = get_object_or_404(Group, uuid=group_uuid)
        user = request.user
        group.members.add(user)
        return redirect("group", uuid=group.uuid)
    return redirect("index")


@require_POST
@login_required
def add_user_score(request: HttpRequest) -> HttpResponse:
    user = request.user
    movie_id = request.POST.get("movie_id")
    group_uuid = request.POST.get("group_uuid")
    user_score = request.POST.get("score")

    if group_uuid and user_score and movie_id:
        group = get_object_or_404(Group, uuid=group_uuid)
        movie = get_object_or_404(Movie, tmdb_id=movie_id)
        group_movie = get_object_or_404(GroupMovie, group=group, movie=movie)
        user_score = Review.objects.update_or_create(
            group_movie=group_movie,
            user=user,
            defaults={"score": user_score},
        )

        # Reviewing implies the reviewer has watched it personally.
        # Personal scope only: never mutates GroupMovie.status by itself.
        from movies.services import mark_personally_watched

        mark_personally_watched(user, movie)

        avg_score = Review.objects.filter(group_movie=group_movie).aggregate(Avg("score"))["score__avg"]
        group_movie.average_score = avg_score

        scores_count = Review.objects.filter(group_movie=group_movie).count()
        if scores_count >= 2 or scores_count == group.members.count():
            group_movie.status = GroupMovie.Status.WATCHED

        group_movie.save()

        return redirect("group", uuid=group.uuid)

    return JsonResponse({"error": "Missing parameter to set score"}, status=400)


@require_POST
@login_required
def leave_group(request: HttpRequest) -> HttpResponse:
    user = request.user
    group_uuid = request.POST.get("group_uuid")

    if group_uuid:
        group = get_object_or_404(Group, uuid=group_uuid)
        if user in group.members.all():
            group.members.remove(user)
            return redirect("profile")

    return redirect("profile")


@group_member_required
def group_info(request: HttpRequest, uuid: uuid.UUID) -> HttpResponse:
    group = get_object_or_404(Group, uuid=uuid)

    group_memberships = GroupMembership.objects.filter(group=group).select_related("user")
    group_movies = GroupMovie.objects.filter(group=group)
    watched_movies_count = group_movies.filter(status=GroupMovie.Status.WATCHED).count()
    not_watched_movies_count = group_movies.filter(status=GroupMovie.Status.SUGGESTED).count()

    user_scores_info = (
        Review.objects.filter(group_movie__group=group)
        .values("user__username")
        .annotate(score_count=Count("score"), avg_score=Round(Avg("score"), 1))
    )

    context = {
        "group": group,
        "group_membership": group_memberships,
        "group_movies_count": group_movies.count(),
        "watched_movies_count": watched_movies_count,
        "not_watched_movies_count": not_watched_movies_count,
        "user_scores_info": user_scores_info,
    }

    return render(request, "group_info.html", context)
