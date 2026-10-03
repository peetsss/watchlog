"""Thin HTTP views for the lobby; all transitions delegate to services."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from groups.models import Group
from movies.catalog import resolve_movie

from . import recommender, services
from .models import LobbySession


def _get_session_for_user(session_id, user) -> LobbySession:
    session = get_object_or_404(LobbySession.objects.select_related("group"), pk=session_id)
    if not session.group.members.filter(pk=user.pk).exists():
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("group members only")
    return session


@login_required
def lobby_active(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    state = services.get_session_state(session, request.user)
    return render(request, "lobby_active.html", {"session": session, "state": state})


@login_required
def lobby_waiting(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    participants = session.participants.select_related("user")
    is_host = session.host_id == request.user.pk
    return render(
        request,
        "lobby_waiting.html",
        {
            "session": session,
            "participants": participants,
            "is_host": is_host,
            "questions": session.quiz_snapshot.get("questions", []),
        },
    )


@require_POST
@login_required
def lobby_create(request):
    group = get_object_or_404(Group, uuid=request.POST.get("group_uuid"))
    try:
        session = services.create_session(group, request.user)
    except services.LobbyError as exc:
        messages.error(request, str(exc))
        return redirect("group", uuid=group.uuid)
    return redirect("lobby:waiting", session_id=session.id)


@require_POST
@login_required
def lobby_join(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    try:
        services.join_session(session, request.user)
    except services.LobbyError as exc:
        messages.error(request, str(exc))
    return redirect("lobby:waiting", session_id=session.id)


@require_POST
@login_required
def lobby_answer(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    answers = {k[7:]: v for k, v in request.POST.items() if k.startswith("answer_")}
    try:
        services.submit_quiz_answers(session, request.user, answers)
    except services.LobbyError as exc:
        messages.error(request, str(exc))
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("lobby:waiting", session_id=session.id)


@require_POST
@login_required
def lobby_start(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    try:
        session = services.start_session(session, request.user)
    except services.LobbyError as exc:
        messages.error(request, str(exc))
        return redirect("lobby:waiting", session_id=session.id)
    # Refill outside any row lock; recommender handles network + fallback.
    try:
        recommender.refill_session(session)
    except Exception:
        pass
    session.refresh_from_db()
    if session.cards.filter(status="current").exists():
        return redirect("lobby:active", session_id=session.id)
    messages.error(request, "No candidates available yet; nominate a movie below.")
    return redirect("lobby:waiting", session_id=session.id)


@require_POST
@login_required
def ballot_submit(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    try:
        services.submit_ballot(
            session,
            request.user,
            request.POST.get("choice", ""),
            card_id=int(request.POST["card_id"]) if request.POST.get("card_id") else None,
        )
    except (services.LobbyError, ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect("lobby:active", session_id=session.id)


@require_POST
@login_required
def manual_nominate(request, session_id):
    session = _get_session_for_user(session_id, request.user)
    tmdb_id = request.POST.get("tmdb_id")
    media_type = request.POST.get("media_type") or "movie"
    if not tmdb_id:
        messages.error(request, "Missing TMDB title.")
        return redirect("lobby:waiting", session_id=session.id)
    movie = resolve_movie(tmdb_id, media_type)
    if movie is None:
        messages.error(request, "Could not resolve that title from TMDB.")
        return redirect("lobby:waiting", session_id=session.id)
    try:
        services.nominate_manual_movie(session, request.user, movie)
    except services.LobbyError as exc:
        messages.error(request, str(exc))
    target = "lobby:active" if session.status == LobbySession.Status.ACTIVE else "lobby:waiting"
    return redirect(target, session_id=session.id)


@require_POST
@login_required
def offer_respond(request, offer_id):
    try:
        response = services.respond_to_offer(offer_id, request.user, request.POST.get("response", ""))
    except services.LobbyError as exc:
        messages.error(request, str(exc))
        return redirect("personal_library")
    session_id = response.offer.card.session_id
    return redirect("lobby:active", session_id=session_id)
