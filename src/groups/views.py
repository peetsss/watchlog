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
from .models import Group, GroupMembership, GroupMovie, UserScore


@login_required
def create_group(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            user = request.user
            group.members.add(user)
            return redirect("group", slug=group.slug)

    form = GroupForm()
    return redirect("index")


@login_required
@group_member_required
def generate_invite_link(request: HttpRequest, slug: str) -> JsonResponse:
    group = get_object_or_404(Group, slug=slug)
    invite_link = request.build_absolute_uri(reverse("join_group_by_link", kwargs={"code": group.code}))
    return JsonResponse({"invite_link": invite_link})


@login_required
def join_group_by_link(request: HttpRequest, code: str) -> HttpResponse:
    group = get_object_or_404(Group, code=code)
    user = request.user
    if user not in group.members.all():
        group.members.add(user)
    return redirect("group", slug=group.slug)


@group_member_required
def group_view(request: HttpRequest, slug: str) -> HttpResponse:
    group = get_object_or_404(Group, slug=slug)
    group_movies = GroupMovie.objects.filter(group=group)
    user_scores_queryset = UserScore.objects.filter(group=group).select_related("user")

    user_scores = {}
    for score in user_scores_queryset:
        movie_id = score.movie.imdb_id
        if movie_id not in user_scores:
            user_scores[movie_id] = []
        user_scores[movie_id].append((score.user.username, score.score))

    watched_movies = group_movies.filter(watched=True)
    not_watched_movies = group_movies.filter(watched=False)
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
    code = request.POST.get("code")
    if code:
        group = get_object_or_404(Group, code=code)
        user = request.user
        group.members.add(user)
        return redirect("group", slug=group.slug)
    return redirect("index")


@require_POST
@login_required
def add_user_score(request: HttpRequest) -> HttpResponse:
    ""
    user = request.user
    movie_id = request.POST.get("movie_id")
    group_code = request.POST.get("group_code")
    user_score = request.POST.get("score")

    if group_code and user_score and movie_id:
        group = get_object_or_404(Group, code=group_code)
        movie = get_object_or_404(Movie, imdb_id=movie_id)
        user_score = UserScore.objects.update_or_create(
            user=user,
            movie=movie,
            group=group,
            defaults={"score": user_score},
        )

        group_movie = get_object_or_404(GroupMovie, group=group, movie=movie)
        avg_score = UserScore.objects.filter(movie=movie, group=group).aggregate(Avg("score"))["score__avg"]
        group_movie.average_score = avg_score

        scores_count = UserScore.objects.filter(movie=movie, group=group).count()
        if scores_count >= 2 or scores_count == group.members.count():
            group_movie.watched = True

        group_movie.save()

        return redirect("group", slug=group.slug)

    return JsonResponse({"error": "Missing parameter to set score"}, status=400)


@require_POST
@login_required
def leave_group(request: HttpRequest) -> HttpResponse:
    user = request.user
    group_code = request.POST.get("group_code")

    if group_code:
        group = get_object_or_404(Group, code=group_code)
        if user in group.members.all():
            group.members.remove(user)
            return redirect("profile")

    return redirect("profile")


@group_member_required
def group_info(request: HttpRequest, slug: str) -> HttpResponse:
    group = get_object_or_404(Group, slug=slug)

    group_memberships = GroupMembership.objects.filter(group=group).select_related("user")
    group_movies = GroupMovie.objects.filter(group=group)
    watched_movies_count = group_movies.filter(watched=True).count()
    not_watched_movies_count = group_movies.filter(watched=False).count()

    user_scores_info = (
        UserScore.objects.filter(group=group).values("user__username").annotate(score_count=Count("score"), avg_score=Round(Avg("score"), 1))
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
