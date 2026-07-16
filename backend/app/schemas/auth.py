"""Auth + User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import SCOPES
from app.schemas.common import ORMBase


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # seconds


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=128)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None  # optional; revoke nếu có


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserRead(ORMBase):
    id: str
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_superuser: bool
    scopes: list[str]
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    scopes: list[str] | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    scopes: list[str] = Field(
        default_factory=lambda: [
            "jobs:read",
            "jobs:write",
            "jobs:run",
            "results:read",
            "results:export",
        ]
    )
    is_superuser: bool = False

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, v: list[str]) -> list[str]:
        invalid = [s for s in v if s not in SCOPES and s != "*"]
        if invalid:
            raise ValueError(f"invalid scopes: {invalid}")
        return v
