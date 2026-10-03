from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from groups.models import Group, GroupMovie
from movies.utils.tmdb import TMDBClient

from . import services
from .catalog import resolve_movie
from .models import Movie


@require_POST
@login_required
def search_movies(request: HttpRequest) -> JsonResponse:
    query = request.POST.get("query")
    if query:
        with TMDBClient() as client:
            movies = client.search(query)
        if movies is None:
            return JsonResponse({"error": "TMDB request failed."}, status=502)
        return JsonResponse({"movies": movies})

    return JsonResponse({"error": "No query parameter provided."}, status=400)


@require_POST
@login_required
def add_movie(request: HttpRequest) -> HttpResponse:
    user = request.user
    movie_id = request.POST.get("movie_id")
    media_type = request.POST.get("media_type") or Movie.MediaType.MOVIE
    group_uuid = request.POST.get("group_uuid")

    if not movie_id or not group_uuid:
        return HttpResponseBadRequest("Missing parameters")
    if media_type not in Movie.MediaType.values:
        return HttpResponseBadRequest("Invalid media type")

    group = get_object_or_404(Group, uuid=group_uuid)
    try:
        movie = resolve_movie(movie_id, media_type)
    except ValueError:
        return HttpResponseBadRequest("Invalid media type")
    if movie is None:
        return HttpResponseBadRequest("Failed to fetch movie details from TMDB.")

    GroupMovie.objects.get_or_create(group=group, movie=movie, defaults={"suggested_by": user})

    return JsonResponse({"msg": f"{movie.title} has been added to {group.name}"}, status=200)


@login_required
def personal_library(request: HttpRequest) -> HttpResponse:
    """Private Want-to-watch + Watched lists; owner-scoped, never shared."""
    watchlist = services.get_personal_watchlist(request.user)
    history = services.get_personal_history(request.user)
    return render(
        request,
        "personal_library.html",
        {"watchlist_entries": watchlist, "history_entries": history},
    )


@require_POST
@login_required
def personal_watchlist_add(request: HttpRequest) -> HttpResponse:
    movie = get_object_or_404(Movie, pk=request.POST.get("movie_id"))
    services.add_to_personal_watchlist(request.user, movie)
    redirect_to = request.POST.get("next") or "personal_library"
    return redirect(redirect_to)


@require_POST
@login_required
def personal_watchlist_remove(request: HttpRequest) -> HttpResponse:
    movie = get_object_or_404(Movie, pk=request.POST.get("movie_id"))
    services.remove_from_personal_watchlist(request.user, movie)
    redirect_to = request.POST.get("next") or "personal_library"
    return redirect(redirect_to)


@require_POST
@login_required
def personal_mark_watched(request: HttpRequest) -> HttpResponse:
    movie = get_object_or_404(Movie, pk=request.POST.get("movie_id"))
    services.mark_personally_watched(request.user, movie)
    redirect_to = request.POST.get("next") or "personal_library"
    return redirect(redirect_to)
