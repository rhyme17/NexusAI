from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def build_error_detail(
    *,
    error_code: str,
    user_message: str,
    operation: str,
    detail: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    task_status: str | None = None,
    retryable: bool | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error_code": error_code,
        "user_message": user_message,
        "operation": operation,
    }
    if detail:
        payload["detail"] = detail
    if task_id:
        payload["task_id"] = task_id
    if agent_id:
        payload["agent_id"] = agent_id
    if task_status:
        payload["task_status"] = task_status
    if retryable is not None:
        payload["retryable"] = retryable
    if extras:
        payload.update(extras)
    return payload


def raise_api_error(
    status_code: int,
    *,
    error_code: str,
    user_message: str,
    operation: str,
    detail: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    task_status: str | None = None,
    retryable: bool | None = None,
    extras: dict[str, Any] | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=build_error_detail(
            error_code=error_code,
            user_message=user_message,
            operation=operation,
            detail=detail,
            task_id=task_id,
            agent_id=agent_id,
            task_status=task_status,
            retryable=retryable,
            extras=extras,
        ),
    )
