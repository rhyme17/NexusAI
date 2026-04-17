from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.agents import router as agents_router
from .api.auth import router as auth_router
from .api.auto_discover import router as auto_discover_router
from .api.debug import router as debug_router
from .api.events import router as events_router
from .api.tasks import router as tasks_router
from .core.api_errors import build_error_detail
from .core.config import get_api_auth_keys, get_storage_backend, is_api_auth_enabled, is_read_only_mode_enabled, resolve_api_key_role
from .core.security import (
    build_auth_misconfigured_detail,
    build_unauthorized_detail,
    extract_api_key,
    extract_bearer_token,
    is_exempt_path,
)
from .middleware.audit import build_audit_payload, emit_audit_log, now, resolve_actor, resolve_request_id
from .core.startup import apply_startup_clear_if_enabled
from .services.message_bus import get_message_bus
from .services.auth_service import get_auth_service
from .services.store import get_store


def _get_cors_origins() -> list[str]:
    raw = os.getenv("NEXUSAI_CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    apply_startup_clear_if_enabled(store=get_store(), bus=get_message_bus())
    yield

app = FastAPI(
    title="NexusAI API",
    description="API for multi-agent orchestration, operations, and productization rollout.",
    version="0.1.0",
    lifespan=app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"message": "NexusAI backend is running"}


@app.get("/health", tags=["system"])
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "read_only": is_read_only_mode_enabled(),
        "storage_backend": get_storage_backend(),
    }


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    request_id = resolve_request_id(request)
    started = now()
    provided_api_key = extract_api_key(request)
    bearer_token = extract_bearer_token(request)
    request.state.auth_api_key = provided_api_key
    request.state.auth_user = None
    request.state.auth_role = None
    request.state.auth_actor = None
    response = None

    def _try_auth_user_from_token() -> bool:
        if not bearer_token:
            return False
        user = get_auth_service().get_user_by_token(bearer_token)
        if not user:
            return False
        request.state.auth_user = user
        request.state.auth_role = user.role.value
        request.state.auth_actor = f"user:{user.username}/{user.role.value}"
        return True

    has_bearer_user = _try_auth_user_from_token()

    if not is_api_auth_enabled() or is_exempt_path(request.url.path):
        response = await call_next(request)
    else:
        allowed_api_keys = get_api_auth_keys()
        if not allowed_api_keys:
            if has_bearer_user:
                response = await call_next(request)
            else:
                response = JSONResponse(status_code=503, content={"detail": build_auth_misconfigured_detail()})
        elif has_bearer_user:
            response = await call_next(request)
        elif provided_api_key is not None and provided_api_key in allowed_api_keys:
            request.state.auth_role = resolve_api_key_role(provided_api_key)
            response = await call_next(request)
        else:
            response = JSONResponse(status_code=401, content={"detail": build_unauthorized_detail()})

    if response is None:
        response = await call_next(request)

    if (
        response.status_code < 400
        and is_read_only_mode_enabled()
        and request.url.path.startswith("/api/")
        and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
    ):
        response = JSONResponse(
            status_code=503,
            content={
                "detail": build_error_detail(
                    error_code="E_SYSTEM_READ_ONLY",
                    user_message="系统当前处于只读维护模式，暂不接受写入操作。",
                    operation="read_only_mode",
                    detail="System is in read-only maintenance mode",
                    retryable=True,
                    extras={
                        "read_only": True,
                        "method": request.method,
                        "path": request.url.path,
                    },
                )
            },
        )

    response.headers["X-Request-ID"] = request_id
    duration_ms = (now() - started) * 1000
    emit_audit_log(
        build_audit_payload(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            actor=getattr(request.state, "auth_actor", None)
            or resolve_actor(provided_api_key, getattr(request.state, "auth_role", None)),
        )
    )
    return response


app.include_router(tasks_router)
app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(auto_discover_router)
app.include_router(debug_router)
app.include_router(events_router)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Phase A API key header used for protected /api routes",
    }

    for path, methods in schema.get("paths", {}).items():
        if not path.startswith("/api/"):
            continue
        if path.startswith("/api/auth"):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            operation.setdefault("security", [{"ApiKeyAuth": []}])
            responses = operation.setdefault("responses", {})
            responses.setdefault(
                "401",
                {
                    "description": "Unauthorized - missing or invalid X-API-Key",
                },
            )

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi



