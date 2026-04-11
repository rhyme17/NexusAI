from __future__ import annotations

from fastapi import HTTPException, Request

from .config import get_api_auth_exempt_paths, is_api_auth_enabled


def extract_api_key(request: Request) -> str | None:
    candidate = request.headers.get("X-API-Key")
    if candidate and candidate.strip():
        return candidate.strip()
    return None


def extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme != "bearer" or not token:
        return None
    return token


def is_exempt_path(path: str) -> bool:
    normalized = path.strip() or "/"
    if normalized == "/api/auth" or normalized.startswith("/api/auth/"):
        return True
    for exempt in get_api_auth_exempt_paths():
        if exempt == "/":
            if normalized == "/":
                return True
            continue
        if normalized == exempt or normalized.startswith(f"{exempt}/"):
            return True
    return False


def build_unauthorized_detail() -> dict[str, object]:
    return {
        "error_code": "E_AUTH_UNAUTHORIZED",
        "user_message": "Missing or invalid API key.",
        "operation": "api_auth",
        "detail": "Provide a valid X-API-Key header or Authorization: Bearer <token>",
        "retryable": False,
    }


def build_auth_misconfigured_detail() -> dict[str, object]:
    return {
        "error_code": "E_AUTH_CONFIG",
        "user_message": "Server auth is enabled but no API keys are configured.",
        "operation": "api_auth",
        "detail": "Set NEXUSAI_API_KEYS with one or more keys",
        "retryable": False,
    }


def build_forbidden_detail(*, required_roles: list[str], actual_role: str | None) -> dict[str, object]:
    expected = ", ".join(required_roles)
    return {
        "error_code": "E_AUTH_FORBIDDEN",
        "user_message": "Insufficient role for this operation.",
        "operation": "role_guard",
        "detail": f"Requires one of: {expected}",
        "required_roles": required_roles,
        "actual_role": actual_role or "unknown",
        "retryable": False,
    }


def get_request_role(request: Request) -> str | None:
    return getattr(request.state, "auth_role", None)


def ensure_request_role(request: Request, *, allowed_roles: set[str]) -> None:
    if not is_api_auth_enabled():
        return
    actual_role = get_request_role(request)
    if actual_role in allowed_roles:
        return
    raise HTTPException(
        status_code=403,
        detail=build_forbidden_detail(required_roles=sorted(allowed_roles), actual_role=actual_role),
    )


