from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "index.html")


@require_GET
def health(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")
