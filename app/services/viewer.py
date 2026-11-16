import re
import zlib

from app.models.user import User
from app.schemas.auth import Viewer

VIEWER_TONES = ("#d09a83", "#9bb39a", "#8fa6bf", "#e7b45a", "#b79ac9")


def initials_for(name: str) -> str:
    parts = [part for part in re.split(r"[\s._-]+", name.strip()) if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


def color_for(value: int | str) -> str:
    if isinstance(value, int):
        index = value % len(VIEWER_TONES)
    else:
        index = zlib.crc32(value.encode("utf-8")) % len(VIEWER_TONES)
    return VIEWER_TONES[index]


def viewer_for(user: User) -> Viewer:
    return Viewer(
        mode="member",
        id=user.id,
        username=user.username,
        initials=initials_for(user.username),
        color=color_for(user.id),
    )
