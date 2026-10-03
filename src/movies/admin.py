from django.contrib import admin

from .models import Movie, UserMovieLibrary


@admin.register(UserMovieLibrary)
class UserMovieLibraryAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "watchlist_added_at", "first_watched_at")
    list_filter = ("watchlist_added_at", "first_watched_at")
    search_fields = ("user__username", "movie__title")


# Register your models here.
admin.site.register(Movie)
