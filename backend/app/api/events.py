import asyncio
from queue import Empty, Queue

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..models.message import BusMessage
from ..services.message_bus import InMemoryMessageBus, get_message_bus

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
) -> None:
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

