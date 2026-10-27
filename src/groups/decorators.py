from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from .models import Group


def group_member_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        uuid = kwargs.get("uuid")
        if not uuid:
            messages.error(request, "Group id is missing.")
            return redirect("index")

        group = get_object_or_404(Group, uuid=uuid)
        if group.members.filter(pk=request.user.pk).exists():
            return view_func(request, *args, **kwargs)

        messages.error(request, "You are not authorized to view this group.")
        return redirect("index")

    return wrapper
