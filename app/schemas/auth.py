from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


def _validate_new_password(value: str) -> str:
    if value.isdigit():
        raise ValueError("Password must not be entirely numeric")
    return value


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=150, pattern=USERNAME_PATTERN)
    email: EmailStr
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
        if isinstance(username, str) and value.lower() == username.lower():
            raise ValueError("Password must not match the username")
        return _validate_new_password(value)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier", mode="before")
    @classmethod
    def strip_identifier(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_new_password(value)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_new_password(value)


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Viewer(BaseModel):
    mode: Literal["member"]
    id: int
    username: str
    initials: str
    color: str
    email_verified: bool


class ViewerEnvelope(BaseModel):
    viewer: Viewer


class ViewerStats(BaseModel):
    titles_watched: int
    average_score: float | None


class MeEnvelope(BaseModel):
    viewer: Viewer
    stats: ViewerStats
    email: str | None


class AccountEnvelope(BaseModel):
    username: str
    email: str | None
    email_verified: bool
    pending_email: str | None


class CSRFResponse(BaseModel):
    csrf_token: str = Field(serialization_alias="csrfToken")
