from dataclasses import dataclass
from uuid import UUID

from app.models.guest import Guest
from app.models.user import User


@dataclass(frozen=True)
class Viewer:
    user: User | None = None
    guest: Guest | None = None

    def __post_init__(self) -> None:
        if (self.user is None) == (self.guest is None):
            raise ValueError("A viewer must be exactly one of a member or a guest")

    @classmethod
    def for_user(cls, user: User) -> Viewer:
        return cls(user=user)

    @classmethod
    def for_guest(cls, guest: Guest) -> Viewer:
        return cls(guest=guest)

    @property
    def is_guest(self) -> bool:
        return self.guest is not None

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user is not None else None

    @property
    def guest_id(self) -> UUID | None:
        return self.guest.id if self.guest is not None else None

    @property
    def display_name(self) -> str:
        if self.user is not None:
            return self.user.username
        if self.guest is not None:
            return self.guest.display_name
        raise RuntimeError("A viewer must have an identity")

    @property
    def identity_key(self) -> str:
        if self.user is not None:
            return f"user:{self.user.id}"
        if self.guest is not None:
            return f"guest:{self.guest.id}"
        raise RuntimeError("A viewer must have an identity")
