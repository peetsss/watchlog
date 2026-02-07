from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from groups.models import Group, GroupMovie
from movies.utils.imdb import IMDbClient
from movies.utils.utils import get_metacritic_url, get_rotten_url

from .models import Movie


@require_POST
@login_required
def search_movies(request: HttpRequest) -> JsonResponse:
    query = request.POST.get("query")
    if query:
        movies = IMDbClient.fetch_search_query(query=query)
        return JsonResponse({"movies": movies})

    return JsonResponse({"error": "No query parameter provided."}, status=400)


@require_POST
@login_required
def add_movie(request: HttpRequest) -> HttpResponse:
    user = request.user
    movie_id = request.POST.get("movie_id")
    group_code = request.POST.get("group_code")

    if not movie_id or not group_code:
        return HttpResponseBadRequest("Missing parameters")

    group = get_object_or_404(Group, code=group_code)
    movie = Movie.objects.filter(imdb_id=movie_id).first()

    if not movie:
        movie_details = IMDbClient.fetch_movie_details(movie_id)
        if not movie_details:
            return HttpResponseBadRequest("Failed to fetch movie details from IMDb.")

        released_date = movie_details.get("Released")
        if released_date:
            released_date = datetime.strptime(released_date, "%d %b %Y").date()

        title = movie_details.get("Title")
        type = movie_details.get("Type")

        imdb_url = f"https://www.imdb.com/title/{movie_id}"
        rottentomato_url = get_rotten_url(title, type)
        metacritic_url = get_metacritic_url(title, type)

        movie = Movie.objects.create(
            imdb_id=movie_id,
            title=title,
            type=type,
            description=movie_details.get("Plot"),
            year=released_date,
            genre=movie_details.get("Genre"),
            director=movie_details.get("Director"),
            writers=movie_details.get("Writer"),
            actors=movie_details.get("Actors"),
            country=movie_details.get("Country"),
            poster=movie_details.get("Poster"),
            awards=movie_details.get("Awards"),
            imdb_score=movie_details.get("imdbRating", "N/A"),
            rottentomato_score=movie_details["Ratings"][1]["Value"] if len(movie_details.get("Ratings", [])) > 1 else "N/A",
            metacritic_score=movie_details.get("Metascore", "N/A"),
            filmweb_score=None,
            imdb_url=imdb_url,
            rottentomato_url=rottentomato_url,
            metacritic_url=metacritic_url,
            filmweb_url=None,
        )

    GroupMovie.objects.get_or_create(group=group, movie=movie, added_by=user.username)

    return JsonResponse(
        {"msg": f"{movie.title} has been added to {group.name}"},
        status=200,
    )
