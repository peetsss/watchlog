def user_groups(request):
    user = request.user
    if user.is_authenticated:
        groups = user.movie_groups.all()
    else:
        groups = None
    return {"groups": groups}
