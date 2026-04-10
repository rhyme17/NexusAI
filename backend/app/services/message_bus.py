from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from ..core.config import get_event_history_limit, get_events_file, is_json_persistence_enabled
from ..models.message import BusMessage, MessageType
from .json_persistence import load_json_file, merge_json_object_atomic, write_json_file_atomic


class InMemoryMessageBus:
    """Simple in-process pub/sub bus for task-scoped events."""

    def __init__(
        self,
        *,
        persistence_enabled: bool | None = None,
        events_file: Path | None = None,
    ) -> None:
        self._task_subscribers: dict[str, dict[str, Queue[BusMessage]]] = {}
        self._subscriber_task_index: dict[str, str] = {}
        self._task_event_history: dict[str, list[BusMessage]] = {}
        self._history_limit = get_event_history_limit()
        self._lock = Lock()
        self._persistence_enabled = is_json_persistence_enabled() if persistence_enabled is None else persistence_enabled
        self._events_file = events_file or get_events_file()
        self._load_event_history()

    def _load_event_history(self) -> None:
        if not self._persistence_enabled:
            return
        raw_history = load_json_file(self._events_file, default_factory=dict)
        if not isinstance(raw_history, dict):
            return

        loaded: dict[str, list[BusMessage]] = {}
        for task_id, messages in raw_history.items():
            if not isinstance(task_id, str) or not isinstance(messages, list):
                continue
            restored_messages: list[BusMessage] = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                try:
                    restored_messages.append(BusMessage.model_validate(message))
                except Exception:
                    continue
            if len(restored_messages) > self._history_limit:
                restored_messages = restored_messages[-self._history_limit :]
            loaded[task_id] = restored_messages
        self._task_event_history = loaded

    def _persist_event_history(self) -> None:
        if not self._persistence_enabled:
            return
        with self._lock:
            snapshot = {
                task_id: [message.model_dump(mode="json") for message in messages]
                for task_id, messages in self._task_event_history.items()
            }
        write_json_file_atomic(self._events_file, snapshot)

    def subscribe_task(self, task_id: str) -> tuple[str, Queue[BusMessage]]:
        subscriber_id = f"sub_{uuid4().hex[:8]}"
        queue: Queue[BusMessage] = Queue()
        with self._lock:
            self._task_subscribers.setdefault(task_id, {})[subscriber_id] = queue
            self._subscriber_task_index[subscriber_id] = task_id
        return subscriber_id, queue

    def unsubscribe(self, subscriber_id: str) -> None:
        with self._lock:
            task_id = self._subscriber_task_index.pop(subscriber_id, None)
            if not task_id:
                return
            subscribers = self._task_subscribers.get(task_id)
            if not subscribers:
                return
            subscribers.pop(subscriber_id, None)
            if not subscribers:
                self._task_subscribers.pop(task_id, None)

    def publish(self, message: BusMessage) -> None:
        self.publish_many([message])

    def publish_many(self, messages: list[BusMessage]) -> None:
        task_messages = [message for message in messages if message.task_id]
        if not task_messages:
            return

        touched_task_ids: set[str] = set()
        snapshot_to_persist: dict[str, list[dict[str, Any]]] | None = None
        delivery_queue: list[tuple[BusMessage, list[Queue[BusMessage]]]] = []
        with self._lock:
            for message in task_messages:
                history = self._task_event_history.setdefault(message.task_id, [])
                history.append(message)
                if len(history) > self._history_limit:
                    del history[: len(history) - self._history_limit]
                touched_task_ids.add(message.task_id)
                subscribers = list(self._task_subscribers.get(message.task_id, {}).values())
                delivery_queue.append((message, subscribers))
            if self._persistence_enabled:
                snapshot_to_persist = {
                    task_id: [item.model_dump(mode="json") for item in self._task_event_history.get(task_id, [])]
                    for task_id in touched_task_ids
                }

        if snapshot_to_persist is not None:
            merge_json_object_atomic(self._events_file, snapshot_to_persist)

        for message, subscribers in delivery_queue:
            for subscriber_queue in subscribers:
                subscriber_queue.put(message)

    def list_task_events(
        self,
        task_id: str,
        offset: int = 0,
        limit: int = 200,
        event_types: list[MessageType] | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: Literal["asc", "desc"] = "asc",
    ) -> tuple[list[BusMessage], int]:
        with self._lock:
            events = self._task_event_history.get(task_id, [])
            if event_types:
                allowed = set(event_types)
                events = [event for event in events if event.type in allowed]
            if from_time is not None:
                events = [event for event in events if event.timestamp >= from_time]
            if to_time is not None:
                events = [event for event in events if event.timestamp <= to_time]
            if sort == "desc":
                events = list(reversed(events))

            total = len(events)
            return list(events[offset : offset + limit]), total

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "events": {
                    task_id: [message.model_dump(mode="json") for message in messages]
                    for task_id, messages in self._task_event_history.items()
                }
            }

    def import_snapshot(self, snapshot: dict[str, Any]) -> dict[str, int]:
        raw_events = snapshot.get("events", {}) if isinstance(snapshot, dict) else {}
        loaded: dict[str, list[BusMessage]] = {}
        if isinstance(raw_events, dict):
            for task_id, messages in raw_events.items():
                if not isinstance(task_id, str) or not isinstance(messages, list):
                    continue
                restored_messages: list[BusMessage] = []
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    try:
                        restored_messages.append(BusMessage.model_validate(message))
                    except Exception:
                        continue
                if len(restored_messages) > self._history_limit:
                    restored_messages = restored_messages[-self._history_limit :]
                loaded[task_id] = restored_messages

        with self._lock:
            self._task_event_history = loaded
        self._persist_event_history()
        return {
            "tasks_with_events": len(loaded),
            "events": sum(len(items) for items in loaded.values()),
        }

    def clear_history(self, task_id: str | None = None) -> None:
        with self._lock:
            if task_id is None:
                self._task_event_history = {}
            else:
                self._task_event_history.pop(task_id, None)
        if not self._persistence_enabled:
            return
        if task_id is None:
            write_json_file_atomic(self._events_file, {})
            return
        merge_json_object_atomic(self._events_file, {}, remove_keys=[task_id])


_bus = InMemoryMessageBus()


def get_message_bus() -> InMemoryMessageBus:
    return _bus



