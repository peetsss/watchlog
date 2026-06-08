from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from .models import Group


def group_member_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        uuid = kwargs.get("uuid")
        if uuid:
            user = request.user
            group = get_object_or_404(Group, uuid=uuid)
            if user in group.members.all():
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "You are not authorized to view this group.")
                return redirect("index")
        else:
            messages.error(request, "Group slug is missing.")
            return redirect("index")

    return wrapper
