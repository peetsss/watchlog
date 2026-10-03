from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def health(request: "HttpRequest") -> "JsonResponse":
    """Liveness probe for container healthchecks; no auth, no DB."""
    return JsonResponse({"status": "ok"})


@login_required
def index(request: "HttpRequest") -> "HttpResponse":
    return render(request, "index.html")
