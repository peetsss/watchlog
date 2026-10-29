from django.urls import path

from lobby import consumers

websocket_urlpatterns = [
    path("ws/lobby/<uuid:lobby_uuid>/", consumers.LobbyConsumer.as_asgi()),
]
