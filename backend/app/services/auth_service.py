from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from ..core.config import (
    get_auth_bootstrap_admin_password,
    get_auth_bootstrap_admin_username,
    get_auth_file,
    get_auth_session_ttl_hours,
)
from ..core.passwords import hash_password, verify_password
from ..models.auth import InviteCode, SessionToken, User, UserPublic, UserRole


class AuthServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AuthService:
    def __init__(self, *, auth_file: Path | None = None) -> None:
        self._auth_file = auth_file or get_auth_file()
        self._lock = Lock()
        self._users: dict[str, User] = {}
        self._invites: dict[str, InviteCode] = {}
        self._sessions: dict[str, SessionToken] = {}
        self._load()
        self._bootstrap_admin()

    def _load(self) -> None:
        if not self._auth_file.exists() or not self._auth_file.is_file():
            return
        try:
            payload = json.loads(self._auth_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return

        users = payload.get("users", {})
        if isinstance(users, dict):
            for username, raw in users.items():
                if isinstance(username, str) and isinstance(raw, dict):
                    self._users[username.lower()] = User.model_validate(raw)

        invites = payload.get("invites", {})
        if isinstance(invites, dict):
            for code, raw in invites.items():
                if isinstance(code, str) and isinstance(raw, dict):
                    self._invites[code.upper()] = InviteCode.model_validate(raw)

        sessions = payload.get("sessions", {})
        if isinstance(sessions, dict):
            for token, raw in sessions.items():
                if isinstance(token, str) and isinstance(raw, dict):
                    self._sessions[token] = SessionToken.model_validate(raw)

        self._purge_expired_sessions()

    def _persist(self) -> None:
        self._auth_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": {key: value.model_dump(mode="json") for key, value in self._users.items()},
            "invites": {key: value.model_dump(mode="json") for key, value in self._invites.items()},
            "sessions": {key: value.model_dump(mode="json") for key, value in self._sessions.items()},
        }
        self._auth_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _bootstrap_admin(self) -> None:
        username = get_auth_bootstrap_admin_username().strip().lower()
        password = get_auth_bootstrap_admin_password()
        with self._lock:
            existing = self._users.get(username)
            if existing is None:
                self._users[username] = User(
                    user_id=f"user_{uuid4().hex[:10]}",
                    username=username,
                    password_hash=hash_password(password),
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                self._persist()
            elif existing.role != UserRole.ADMIN:
                existing.role = UserRole.ADMIN
                self._persist()

    def _purge_expired_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [token for token, session in self._sessions.items() if session.expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)

    def _purge_inactive_invites(self) -> bool:
        now = datetime.now(timezone.utc)
        stale_codes = [
            code
            for code, invite in self._invites.items()
            if invite.used_count >= invite.max_uses or (invite.expires_at is not None and invite.expires_at <= now)
        ]
        for code in stale_codes:
            self._invites.pop(code, None)
        return bool(stale_codes)

    def _to_public_user(self, user: User) -> UserPublic:
        return UserPublic(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    def get_user_by_username(self, username: str) -> User | None:
        return self._users.get(username.strip().lower())

    def register_user(self, *, username: str, password: str, invite_code: str) -> UserPublic:
        normalized_username = username.strip().lower()
        normalized_invite = invite_code.strip().upper()
        if not normalized_username:
            raise AuthServiceError("E_AUTH_INVALID_USERNAME", "Invalid username")
        if not normalized_invite:
            raise AuthServiceError("E_AUTH_INVITE_REQUIRED", "Invite code is required")

        with self._lock:
            invites_pruned = self._purge_inactive_invites()
            if normalized_username in self._users:
                raise AuthServiceError("E_AUTH_USERNAME_EXISTS", "Username already exists")

            invite = self._invites.get(normalized_invite)
            now = datetime.now(timezone.utc)
            if invite is None:
                if invites_pruned:
                    self._persist()
                raise AuthServiceError("E_AUTH_INVITE_INVALID", "Invite code is invalid")
            if invite.expires_at and invite.expires_at <= now:
                self._invites.pop(normalized_invite, None)
                self._persist()
                raise AuthServiceError("E_AUTH_INVITE_EXPIRED", "Invite code expired")
            if invite.used_count >= invite.max_uses:
                self._invites.pop(normalized_invite, None)
                self._persist()
                raise AuthServiceError("E_AUTH_INVITE_EXHAUSTED", "Invite code exhausted")

            user = User(
                user_id=f"user_{uuid4().hex[:10]}",
                username=normalized_username,
                password_hash=hash_password(password),
                role=UserRole.VIEWER,
                is_active=True,
            )
            invite.used_count += 1
            self._users[normalized_username] = user
            if invite.used_count >= invite.max_uses:
                self._invites.pop(normalized_invite, None)
            else:
                self._invites[normalized_invite] = invite
            self._persist()
            return self._to_public_user(user)

    def create_session(self, *, username: str, password: str) -> tuple[UserPublic, SessionToken]:
        normalized_username = username.strip().lower()
        with self._lock:
            self._purge_expired_sessions()
            user = self._users.get(normalized_username)
            if not user or not user.is_active or not verify_password(password, user.password_hash):
                raise AuthServiceError("E_AUTH_LOGIN_FAILED", "Invalid username or password")

            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=get_auth_session_ttl_hours())
            session = SessionToken(
                token=token,
                user_id=user.user_id,
                username=user.username,
                role=user.role,
                expires_at=expires_at,
            )
            self._sessions[token] = session
            self._persist()
            return self._to_public_user(user), session

    def get_user_by_token(self, token: str | None) -> UserPublic | None:
        if not token:
            return None
        with self._lock:
            self._purge_expired_sessions()
            session = self._sessions.get(token)
            if not session:
                return None
            user = self._users.get(session.username)
            if not user or not user.is_active:
                return None
            return self._to_public_user(user)

    def delete_session(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)
            self._persist()

    def create_invite(
        self,
        *,
        created_by: str,
        max_uses: int = 1,
        expires_hours: int | None = 72,
        code: str | None = None,
    ) -> InviteCode:
        invite_code = (code or f"INV-{secrets.token_hex(4)}").strip().upper()
        if not invite_code:
            raise AuthServiceError("E_AUTH_INVITE_INVALID", "Invite code cannot be empty")
        with self._lock:
            self._purge_inactive_invites()
            if invite_code in self._invites:
                raise AuthServiceError("E_AUTH_INVITE_EXISTS", "Invite code already exists")
            expires_at = None
            if expires_hours is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
            invite = InviteCode(code=invite_code, created_by=created_by, max_uses=max_uses, expires_at=expires_at)
            self._invites[invite_code] = invite
            self._persist()
            return invite

    def list_invites(self) -> list[InviteCode]:
        with self._lock:
            changed = self._purge_inactive_invites()
            if changed:
                self._persist()
            return sorted(self._invites.values(), key=lambda item: item.created_at, reverse=True)

    def revoke_invite(self, *, code: str) -> None:
        normalized = code.strip().upper()
        with self._lock:
            if normalized not in self._invites:
                raise AuthServiceError("E_AUTH_INVITE_INVALID", "Invite code is invalid")
            self._invites.pop(normalized, None)
            self._persist()

    def list_users(self) -> list[UserPublic]:
        with self._lock:
            return sorted((self._to_public_user(user) for user in self._users.values()), key=lambda item: item.created_at)

    def set_user_active(self, *, username: str, is_active: bool, actor_username: str) -> UserPublic:
        normalized = username.strip().lower()
        actor = actor_username.strip().lower()
        with self._lock:
            user = self._users.get(normalized)
            if user is None:
                raise AuthServiceError("E_AUTH_USER_NOT_FOUND", "User not found")
            if user.username == actor and not is_active:
                raise AuthServiceError("E_AUTH_SELF_DISABLE", "Admin cannot disable current session user")
            user.is_active = is_active
            if not is_active:
                # Drop existing sessions for disabled users.
                doomed = [token for token, session in self._sessions.items() if session.username == user.username]
                for token in doomed:
                    self._sessions.pop(token, None)
            self._persist()
            return self._to_public_user(user)

    def reset_user_password(self, *, username: str, new_password: str) -> UserPublic:
        normalized = username.strip().lower()
        with self._lock:
            user = self._users.get(normalized)
            if user is None:
                raise AuthServiceError("E_AUTH_USER_NOT_FOUND", "User not found")
            user.password_hash = hash_password(new_password)
            doomed = [token for token, session in self._sessions.items() if session.username == user.username]
            for token in doomed:
                self._sessions.pop(token, None)
            self._persist()
            return self._to_public_user(user)

    def delete_user_account(self, *, username: str, allow_admin: bool = False) -> None:
        normalized = username.strip().lower()
        with self._lock:
            user = self._users.get(normalized)
            if user is None:
                raise AuthServiceError("E_AUTH_USER_NOT_FOUND", "User not found")
            if user.role == UserRole.ADMIN and not allow_admin:
                raise AuthServiceError("E_AUTH_SELF_DELETE_ADMIN_FORBIDDEN", "Admin account cannot self-delete")
            doomed = [token for token, session in self._sessions.items() if session.username == user.username]
            for token in doomed:
                self._sessions.pop(token, None)
            self._users.pop(normalized, None)
            self._persist()


_auth_service: AuthService | None = None
_auth_signature: tuple[str, str, str] | None = None


def _build_auth_signature() -> tuple[str, str, str]:
    return (
        str(get_auth_file()),
        get_auth_bootstrap_admin_username(),
        get_auth_bootstrap_admin_password(),
    )


def get_auth_service() -> AuthService:
    global _auth_service, _auth_signature
    signature = _build_auth_signature()
    if _auth_service is None or _auth_signature != signature:
        _auth_service = AuthService(auth_file=get_auth_file())
        _auth_signature = signature
    return _auth_service


def reset_auth_service() -> None:
    global _auth_service, _auth_signature
    _auth_service = None
    _auth_signature = None



