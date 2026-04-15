from __future__ import annotations

import asyncio
from queue import Empty, Queue

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..core.config import get_api_auth_keys, is_api_auth_enabled
from ..models.message import BusMessage
from ..services.auth_service import get_auth_service
from ..services.message_bus import InMemoryMessageBus, get_message_bus
from ..services.store import get_store
from ..services.store_contract import StoreContract

router = APIRouter(tags=["events"])


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return


@router.websocket("/ws/tasks/{task_id}")
async def stream_task_events(
    websocket: WebSocket,
    task_id: str,
    bus: InMemoryMessageBus = Depends(get_message_bus),
    store: StoreContract = Depends(get_store),
) -> None:
    user = None
    provided_api_key = _extract_websocket_api_key(websocket)
    if is_api_auth_enabled():
        user = get_auth_service().get_user_by_token(_extract_websocket_token(websocket))
        allowed_api_keys = get_api_auth_keys()
        if user is None:
            if not allowed_api_keys:
                await websocket.close(code=4403, reason="Auth not configured")
                return
            if provided_api_key not in allowed_api_keys:
                await websocket.close(code=4401, reason="Unauthorized")
                return

    task = store.get_task(task_id)
    if not task:
        await websocket.close(code=4404, reason="Task not found")
        return

    if user is not None:
        is_admin = user.role.value == "admin"
        if not is_admin and task.owner_user_id != user.user_id:
            await websocket.close(code=4404, reason="Task not found")
            return
    elif is_api_auth_enabled():
        # Keep websocket visibility consistent with REST behavior for API-key-only callers.
        await websocket.close(code=4404, reason="Task not found")
        return

    await websocket.accept()
    subscriber_id, subscriber_queue = bus.subscribe_task(task_id)
    disconnect_watcher = asyncio.create_task(_wait_for_disconnect(websocket))

    try:
        while True:
            if disconnect_watcher.done():
                break

            message = await asyncio.to_thread(_safe_get, subscriber_queue)
            if message is None:
                continue
            await websocket.send_json(message.model_dump(mode="json"))
    finally:
        disconnect_watcher.cancel()
        bus.unsubscribe(subscriber_id)


def _safe_get(subscriber_queue: Queue[BusMessage], timeout: float = 1.0) -> BusMessage | None:
    try:
        return subscriber_queue.get(timeout=timeout)
    except Empty:
        return None


def _extract_websocket_token(websocket: WebSocket) -> str | None:
    auth_header = websocket.headers.get("authorization")
    if auth_header:
        parts = auth_header.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            if token:
                return token

    cookie_token = websocket.cookies.get("nexusai_auth_token")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    query_token = websocket.query_params.get("access_token")
    if query_token and query_token.strip():
        return query_token.strip()
    return None


def _extract_websocket_api_key(websocket: WebSocket) -> str | None:
    header_key = websocket.headers.get("x-api-key")
    if header_key and header_key.strip():
        return header_key.strip()

    query_key = websocket.query_params.get("api_key")
    if query_key and query_key.strip():
        return query_key.strip()
    return None


