from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=150, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str, info: ValidationInfo) -> str:
        username = info.data.get("username")
        if isinstance(username, str):
            if value.lower() == username.lower():
                raise ValueError("Password must not match the username")
        if value.isdigit():
            raise ValueError("Password must not be entirely numeric")
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Viewer(BaseModel):
    mode: Literal["member"]
    id: int
    username: str
    initials: str
    color: str


class ViewerEnvelope(BaseModel):
    viewer: Viewer


class CSRFResponse(BaseModel):
    csrf_token: str = Field(serialization_alias="csrfToken")
