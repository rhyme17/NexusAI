from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(BaseModel):
    user_id: str
    username: str
    password_hash: str
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserPublic(BaseModel):
    user_id: str
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime


class InviteCode(BaseModel):
    code: str
    created_by: str
    max_uses: int = Field(default=1, ge=1, le=1000)
    used_count: int = Field(default=0, ge=0)
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionToken(BaseModel):
    token: str
    user_id: str
    username: str
    role: UserRole
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=4, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class CreateInviteRequest(BaseModel):
    code: str | None = Field(default=None, min_length=4, max_length=128)
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_hours: int | None = Field(default=72, ge=1, le=24 * 365)


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


