from app.models.user import User
from app.services.viewer import color_for, initials_for, viewer_for


def test_initials_for_usernames() -> None:
    assert initials_for("alice") == "AL"
    assert initials_for("Maya Chen") == "MC"
    assert initials_for("a.b") == "AB"
    assert initials_for("  ") == "?"
    assert initials_for("a") == "A"


def test_color_is_deterministic() -> None:
    assert color_for(1) == color_for(1)
    assert color_for(1) == color_for(6)
    assert color_for("Maya Chen") == color_for("Maya Chen")
    assert color_for("Maya Chen").startswith("#")


def test_viewer_for_user() -> None:
    user = User(id=1, username="alice", password_hash="unused", is_active=True)

    viewer = viewer_for(user)

    assert viewer.mode == "member"
    assert viewer.id == 1
    assert viewer.username == "alice"
    assert viewer.initials == "AL"
    assert viewer.color.startswith("#")
    assert viewer.email_verified is False
