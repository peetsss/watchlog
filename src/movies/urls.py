from django.urls import path

from . import views

urlpatterns = [
    path("search/", views.search_movies, name="search_movies"),
    path("add-movie/", views.add_movie, name="add_movie"),
    path("library/", views.personal_library, name="personal_library"),
    path("library/add/", views.personal_watchlist_add, name="personal_watchlist_add"),
    path("library/remove/", views.personal_watchlist_remove, name="personal_watchlist_remove"),
    path("library/watched/", views.personal_mark_watched, name="personal_mark_watched"),
]
