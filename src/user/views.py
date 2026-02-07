from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Func
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from groups.models import UserScore

from .forms import AuthForm, SignUpForm


def start_view(request: HttpRequest) -> HttpResponse:
    signup_form = SignUpForm()
    login_form = AuthForm()

    auth_mode = "signup" if "signup" in request.POST else "login"
    next_url = request.GET.get("next")

    if request.method == "POST":
        next_url = request.POST.get("next", "")
        if "signup" in request.POST:
            signup_form = SignUpForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save()
                username = signup_form.cleaned_data.get("username")
                raw_password = signup_form.cleaned_data.get("password1")
                user = authenticate(username=username, password=raw_password)
                if user is not None:
                    login(request, user)
                    if next_url:
                        return redirect(next_url)
                    return redirect("index")

        elif "login" in request.POST:
            login_form = AuthForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                if next_url:
                    return redirect(next_url)
                return redirect("index")

    return render(
        request,
        "start.html",
        {
            "signup_form": signup_form,
            "login_form": login_form,
            "auth_mode": auth_mode,
            "next": next_url,
        },
    )


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    user = request.user
    avg_score_across_groups = UserScore.objects.filter(user=user).aggregate(
        avg_score=Func(Avg("score"), function="ROUND", template="%(function)s(%(expressions)s, 1)")
    )

    scores_set_count = UserScore.objects.filter(user=user).aggregate(total_scores=Count("score"))["total_scores"]

    context = {
        "user": user,
        "avg_score_across_groups": avg_score_across_groups,
        "movies_watched_count": scores_set_count,
    }
    return render(request, "profile.html", context)


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("start")
