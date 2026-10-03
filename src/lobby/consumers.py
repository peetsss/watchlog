"""Authenticated lobby websocket consumer.

Thin adapter: authentication, validation, service calls, serialization.
All state transitions live in `lobby.services`; channel fan-out is scheduled
with `transaction.on_commit` there, never here. Ballots stay private: while
incomplete, clients receive only submitted/participant counts plus their own
choice and pending offers.
"""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import services


def _public_state(state: dict) -> dict:
    card = state.get("current_card") or {}
    return {
        "type": "lobby.state",
        "session_id": state["session_id"],
        "status": state["status"],
        "submitted_count": state["submitted_count"],
        "participant_count": state["participant_count"],
        "current_card": (
            {
                "id": card.get("id"),
                "movie_id": card.get("movie_id"),
                "title": card.get("title"),
                "status": card.get("status"),
                "pitch": card.get("pitch"),
            }
            if card
            else None
        ),
        "own_choice": state["own_choice"],
        "pending_offers": state["pending_offers"],
    }


@database_sync_to_async
def _load_session(session_id):
    from .models import LobbySession

    try:
        return LobbySession.objects.select_related("group", "host").get(pk=session_id)
    except LobbySession.DoesNotExist, ValueError, AttributeError:
        return None


@database_sync_to_async
def _authorize(session, user) -> str | None:
    """Return None when allowed, else an error code for close/reject."""
    if session is None:
        return "not_found"
    if not user.is_authenticated:
        return "unauthorized"
    if not session.group.members.filter(pk=user.pk).exists():
        return "forbidden"
    from .models import LobbyParticipant

    if not LobbyParticipant.objects.filter(session=session, user=user).exists():
        return "forbidden"
    return None


@database_sync_to_async
def _get_state(session_id, user):
    from .models import LobbySession

    session = LobbySession.objects.get(pk=session_id)
    return services.get_session_state(session, user)


@database_sync_to_async
def _submit_ballot(session_id, user, choice, card_id):
    from .models import LobbySession

    session = LobbySession.objects.get(pk=session_id)
    result = services.submit_ballot(session, user, choice, card_id=card_id)
    state = services.get_session_state(result.session, user)
    return result, state


@database_sync_to_async
def _submit_quiz(session_id, user, answers):
    from .models import LobbySession

    session = LobbySession.objects.get(pk=session_id)
    services.submit_quiz_answers(session, user, answers)
    return services.get_session_state(session, user)


@database_sync_to_async
def _respond_offer(offer_id, user, action):
    response = services.respond_to_offer(offer_id, user, action)
    session_id = response.offer.card.session_id
    from .models import LobbySession

    session = LobbySession.objects.get(pk=session_id)
    return response, services.get_session_state(session, user)


class LobbyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        session_id = self.scope["url_route"]["kwargs"].get("session_id")
        self.session_id = str(session_id)
        self.group_name = f"lobby_{self.session_id}"
        session = await _load_session(self.session_id)
        error = await _authorize(session, self.scope.get("user"))
        if error == "not_found":
            await self.close(code=4404)
            return
        if error is not None:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        state = await _get_state(self.session_id, self.scope["user"])
        await self.send_json(_public_state(state))

    async def disconnect(self, code):
        group = getattr(self, "group_name", None)
        if group:
            try:
                await self.channel_layer.group_discard(group, self.channel_name)
            except Exception:
                pass
        # Roster stays frozen; disconnects never remove participants.

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        user = self.scope["user"]
        try:
            if action == "state.get":
                state = await _get_state(self.session_id, user)
                await self.send_json(_public_state(state))
            elif action == "quiz.submit":
                state = await _submit_quiz(self.session_id, user, content.get("answers") or {})
                await self.send_json(_public_state(state))
            elif action == "ballot.submit":
                result, state = await _submit_ballot(
                    self.session_id, user, content.get("choice"), content.get("card_id")
                )
                await self.send_json(
                    {
                        **_public_state(state),
                        "type": "lobby.ballot_result",
                        "outcome": result.outcome,
                    }
                )
            elif action == "offer.respond":
                response, state = await _respond_offer(content.get("offer_id"), user, content.get("response"))
                await self.send_json(
                    {**_public_state(state), "type": "lobby.offer_result", "response": response.status}
                )
            else:
                await self.send_json({"type": "lobby.error", "error": f"unknown action: {action!r}"})
        except services.LobbyError as exc:
            await self.send_json({"type": "lobby.error", "error": str(exc)})
        except Exception:
            await self.send_json({"type": "lobby.error", "error": "request failed"})

    # --- Fan-out from services.live (post-commit only) ---
    async def _forward(self, event):
        await self.send_json({"type": event.get("type", "lobby.event"), "event": event})

    async def lobby_created(self, event):
        await self._forward(event)

    async def lobby_started(self, event):
        await self._forward(event)

    async def lobby_nominated(self, event):
        await self._forward(event)

    async def lobby_ballot(self, event):
        await self._forward(event)

    async def lobby_matched(self, event):
        await self._forward(event)

    async def lobby_advanced(self, event):
        await self._forward(event)

    async def lobby_exhausted(self, event):
        await self._forward(event)

    async def lobby_ended(self, event):
        await self._forward(event)

    async def lobby_offer_added(self, event):
        await self._forward(event)

    async def lobby_offer_dismissed(self, event):
        await self._forward(event)
