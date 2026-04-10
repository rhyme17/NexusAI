from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Request

_AUDIT_LOGGER = logging.getLogger("nexusai.audit")


def resolve_request_id(request: Request) -> str:
    candidate = request.headers.get("X-Request-ID")
    if candidate and candidate.strip():
        return candidate.strip()
    return f"req_{uuid4().hex[:12]}"


def _mask_api_key(value: str | None) -> str:
    if not value:
        return "anonymous"
    normalized = value.strip()
    if len(normalized) <= 6:
        return "api_key:***"
    return f"api_key:{normalized[:3]}***{normalized[-2:]}"


def resolve_actor(api_key: str | None, role: str | None = None) -> str:
    masked = _mask_api_key(api_key)
    if role and masked != "anonymous":
        return f"{masked}/{role}"
    return masked


def build_audit_payload(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    actor: str,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 3),
        "actor": actor,
    }


def emit_audit_log(payload: dict[str, Any]) -> None:
    _AUDIT_LOGGER.info(json.dumps(payload, ensure_ascii=False))


def now() -> float:
    return perf_counter()

