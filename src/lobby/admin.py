from django.contrib import admin

from .models import (
    LobbyBallot,
    LobbyCard,
    LobbyParticipant,
    LobbySession,
    WatchlistOffer,
    WatchlistOfferResponse,
)

admin.site.register(LobbySession)
admin.site.register(LobbyParticipant)
admin.site.register(LobbyCard)
admin.site.register(LobbyBallot)
admin.site.register(WatchlistOffer)
admin.site.register(WatchlistOfferResponse)
