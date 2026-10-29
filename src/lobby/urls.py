from django.urls import path

from . import views

app_name = "lobby"

urlpatterns = [
    path("csrf/", views.csrf_view, name="csrf"),
    path("active/", views.active_view, name="active"),
    path("", views.create_view, name="create"),
    path("<uuid:lobby_uuid>/preview/", views.preview_view, name="preview"),
    path("<uuid:lobby_uuid>/join/", views.join_view, name="join"),
    path("<uuid:lobby_uuid>/<str:action>/", views.action_view, name="action"),
    path("<uuid:lobby_uuid>/", views.state_view, name="state"),
]
