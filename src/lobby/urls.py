from django.urls import path

from . import views

app_name = "lobby"

urlpatterns = [
    path("create/", views.lobby_create, name="create"),
    path("<uuid:session_id>/waiting/", views.lobby_waiting, name="waiting"),
    path("<uuid:session_id>/join/", views.lobby_join, name="join"),
    path("<uuid:session_id>/answer/", views.lobby_answer, name="answer"),
    path("<uuid:session_id>/start/", views.lobby_start, name="start"),
    path("<uuid:session_id>/active/", views.lobby_active, name="active"),
    path("<uuid:session_id>/ballot/", views.ballot_submit, name="ballot"),
    path("<uuid:session_id>/nominate/", views.manual_nominate, name="nominate"),
    path("offers/<int:offer_id>/respond/", views.offer_respond, name="offer_respond"),
]
