from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..core.security import extract_bearer_token
from ..services.message_bus import get_message_bus
from ..services.store import get_store
from ..services.store_contract import StoreContract
from ..services.message_bus import InMemoryMessageBus
from ..models.auth import (
    AuthResponse,
    CreateInviteRequest,
    InviteCode,
    LoginRequest,
    RegisterRequest,
    UserPasswordResetRequest,
    UserPublic,
    UserStatusUpdateRequest,
)
from ..services.auth_service import AuthService, AuthServiceError, get_auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _map_auth_error(exc: AuthServiceError) -> HTTPException:
    error_messages = {
        "E_AUTH_INVITE_REQUIRED": "邀请码不能为空。",
        "E_AUTH_INVITE_INVALID": "邀请码无效。",
        "E_AUTH_INVITE_EXPIRED": "邀请码已过期。",
        "E_AUTH_INVITE_EXHAUSTED": "邀请码已使用完毕。",
        "E_AUTH_USERNAME_EXISTS": "用户名已存在。",
        "E_AUTH_LOGIN_FAILED": "用户名或密码错误。",
        "E_AUTH_INVITE_EXISTS": "邀请码已存在。",
        "E_AUTH_USER_NOT_FOUND": "用户不存在。",
        "E_AUTH_SELF_DISABLE": "不能禁用当前管理员账号。",
        "E_AUTH_SELF_DELETE_ADMIN_FORBIDDEN": "管理员账号不能自行注销。",
    }
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "E_AUTH_LOGIN_FAILED":
        status_code = status.HTTP_401_UNAUTHORIZED
    return HTTPException(
        status_code=status_code,
        detail={
            "error_code": exc.code,
            "user_message": error_messages.get(exc.code, exc.message),
            "detail": exc.message,
        },
    )


def _require_user(request: Request, auth_service: AuthService) -> UserPublic:
    token = extract_bearer_token(request)
    user = auth_service.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "E_AUTH_UNAUTHORIZED", "user_message": "请先登录。", "detail": "Invalid or expired token"},
        )
    return user


def _require_admin(request: Request, auth_service: AuthService) -> UserPublic:
    user = _require_user(request, auth_service)
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "E_AUTH_FORBIDDEN", "user_message": "仅管理员可执行该操作。", "detail": "Admin role required"},
        )
    return user


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    try:
        user = auth_service.register_user(
            username=payload.username,
            password=payload.password,
            invite_code=payload.invite_code,
        )
        _, session = auth_service.create_session(username=payload.username, password=payload.password)
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc
    return AuthResponse(access_token=session.token, user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    try:
        user, session = auth_service.create_session(username=payload.username, password=payload.password)
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc
    return AuthResponse(access_token=session.token, user=user)


@router.post("/logout")
def logout(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> dict[str, str]:
    token = extract_bearer_token(request)
    auth_service.delete_session(token)
    return {"status": "ok"}


@router.delete("/me")
def delete_me(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> dict[str, int | str]:
    user = _require_user(request, auth_service)
    if user.role.value == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "E_AUTH_SELF_DELETE_ADMIN_FORBIDDEN",
                "user_message": "管理员账号不能自行注销。",
                "detail": "Admin account cannot self-delete",
            },
        )

    owned_task_ids = [task.task_id for task in store.list_tasks() if task.owner_user_id == user.user_id]
    deleted_tasks = store.delete_tasks_by_owner(user.user_id)
    for task_id in owned_task_ids:
        bus.clear_history(task_id)

    try:
        auth_service.delete_user_account(username=user.username, allow_admin=False)
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc

    return {"status": "deleted", "deleted_tasks": deleted_tasks}


@router.get("/me", response_model=UserPublic)
def me(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> UserPublic:
    return _require_user(request, auth_service)


@router.get("/invites", response_model=list[InviteCode])
def list_invites(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> list[InviteCode]:
    _require_admin(request, auth_service)
    return auth_service.list_invites()


@router.post("/invites", response_model=InviteCode)
def create_invite(
    payload: CreateInviteRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> InviteCode:
    user = _require_admin(request, auth_service)
    try:
        return auth_service.create_invite(
            created_by=user.username,
            max_uses=payload.max_uses,
            expires_hours=payload.expires_hours,
            code=payload.code,
        )
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc


@router.delete("/invites/{code}")
def revoke_invite(
    code: str,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    _require_admin(request, auth_service)
    try:
        auth_service.revoke_invite(code=code)
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc
    return {"status": "ok"}


@router.get("/users", response_model=list[UserPublic])
def list_users(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> list[UserPublic]:
    _require_admin(request, auth_service)
    return auth_service.list_users()


@router.patch("/users/{username}/status", response_model=UserPublic)
def update_user_status(
    username: str,
    payload: UserStatusUpdateRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    admin = _require_admin(request, auth_service)
    try:
        return auth_service.set_user_active(username=username, is_active=payload.is_active, actor_username=admin.username)
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc


@router.post("/users/{username}/reset-password", response_model=UserPublic)
def reset_user_password(
    username: str,
    payload: UserPasswordResetRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    _require_admin(request, auth_service)
    try:
        return auth_service.reset_user_password(username=username, new_password=payload.new_password)
    except AuthServiceError as exc:
        raise _map_auth_error(exc) from exc


