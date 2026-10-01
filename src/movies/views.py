from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from groups.models import Group, GroupMovie
from movies.utils.tmdb import BACKDROP_BASE_URL, POSTER_BASE_URL, TMDBClient

from .models import Movie


def _parse_date(value: str | None) -> datetime | None:
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _join_names(items: list[dict], key: str = "name") -> str | None:
    names = [item[key] for item in items if item.get(key)]
    return ", ".join(names) if names else None


def _full_url(base_url: str, path: str | None) -> str | None:
    return base_url + path if path else None


def _create_movie_from_details(details: dict, media_type: str) -> Movie:
    credits = details.get("credits") or {}
    crew = credits.get("crew") or []
    cast = credits.get("cast") or []
    keywords = (details.get("keywords") or {}).get("keywords") or []
    external_ids = details.get("external_ids") or {}
    runtimes = details.get("episode_run_time") or []
    imdb_id = external_ids.get("imdb_id") or None

    return Movie.objects.create(
        tmdb_id=details["id"],
        imdb_id=imdb_id,
        title=details.get("title") or details.get("name") or "",
        original_title=details.get("original_title") or details.get("original_name") or None,
        media_type=media_type,
        description=details.get("overview") or None,
        status=details.get("status") or None,
        runtime=details.get("runtime") or (runtimes[0] if runtimes else None),
        release_date=_parse_date(details.get("release_date") or details.get("first_air_date")),
        adult=details.get("adult", False),
        genres=_join_names(details.get("genres") or []),
        keywords=_join_names(keywords),
        director=_join_names([c for c in crew if c.get("job") == "Director"]),
        writers=_join_names([c for c in crew if c.get("job") in {"Writer", "Screenplay", "Story"}]),
        actors=_join_names(cast),
        country=_join_names(details.get("production_countries") or []),
        poster_path=_full_url(POSTER_BASE_URL, details.get("poster_path")),
        backdrop_path=_full_url(BACKDROP_BASE_URL, details.get("backdrop_path")),
        tmdb_score=details.get("vote_average"),
        revenue=details.get("revenue") or None,
        budget=details.get("budget") or None,
        imdb_url=f"https://www.imdb.com/title/{imdb_id}" if imdb_id else None,
    )


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
    movie = Movie.objects.filter(tmdb_id=movie_id).first()

    if not movie:
        with TMDBClient() as client:
            details = client.get_details(movie_id, media_type)
        if not details:
            return HttpResponseBadRequest("Failed to fetch movie details from TMDB.")

        movie = _create_movie_from_details(details, media_type)

    GroupMovie.objects.get_or_create(group=group, movie=movie, defaults={"suggested_by": user})

    return JsonResponse({"msg": f"{movie.title} has been added to {group.name}"}, status=200)
