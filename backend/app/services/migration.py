from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .message_bus import InMemoryMessageBus
from .store_contract import StoreContract


def snapshot_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    tasks = snapshot.get("tasks", {}) if isinstance(snapshot, dict) else {}
    agents = snapshot.get("agents", {}) if isinstance(snapshot, dict) else {}
    events = snapshot.get("events", {}) if isinstance(snapshot, dict) else {}
    return {
        "tasks": len(tasks) if isinstance(tasks, dict) else 0,
        "agents": len(agents) if isinstance(agents, dict) else 0,
        "tasks_with_events": len(events) if isinstance(events, dict) else 0,
        "events": sum(len(items) for items in events.values()) if isinstance(events, dict) else 0,
    }


def validate_runtime_snapshot(snapshot: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(snapshot, dict):
        return ["snapshot must be an object"]

    for key in ("tasks", "agents", "events"):
        value = snapshot.get(key)
        if value is None:
            errors.append(f"missing key: {key}")
        elif not isinstance(value, dict):
            errors.append(f"{key} must be an object")

    events = snapshot.get("events")
    if isinstance(events, dict):
        for task_id, items in events.items():
            if not isinstance(task_id, str):
                errors.append("events keys must be task_id strings")
                continue
            if not isinstance(items, list):
                errors.append(f"events[{task_id}] must be an array")

    tasks = snapshot.get("tasks")
    if isinstance(tasks, dict):
        for task_id, payload in tasks.items():
            if not isinstance(task_id, str):
                errors.append("tasks keys must be task_id strings")
                continue
            if not isinstance(payload, dict):
                errors.append(f"tasks[{task_id}] must be an object")
                continue

            metadata = payload.get("metadata", {})
            if not isinstance(metadata, dict):
                errors.append(f"tasks[{task_id}].metadata must be an object")
                continue

            attempts = payload.get("attempt_history", [])
            if not isinstance(attempts, list):
                errors.append(f"tasks[{task_id}].attempt_history must be an array")
            elif not all(isinstance(item, dict) for item in attempts):
                errors.append(f"tasks[{task_id}].attempt_history items must be objects")

            consensus = payload.get("consensus")
            if consensus is not None and not isinstance(consensus, dict):
                errors.append(f"tasks[{task_id}].consensus must be an object or null")

            decomposition = metadata.get("decomposition")
            if decomposition is not None:
                if not isinstance(decomposition, dict):
                    errors.append(f"tasks[{task_id}].metadata.decomposition must be an object")
                    continue
                workflow_run = decomposition.get("workflow_run")
                if workflow_run is not None and not isinstance(workflow_run, dict):
                    errors.append(f"tasks[{task_id}].metadata.decomposition.workflow_run must be an object")
                dag_nodes = decomposition.get("dag_nodes")
                if dag_nodes is not None and not isinstance(dag_nodes, list):
                    errors.append(f"tasks[{task_id}].metadata.decomposition.dag_nodes must be an array")

    return errors


def export_runtime_snapshot(*, store: StoreContract, bus: InMemoryMessageBus) -> dict[str, Any]:
    store_snapshot = store.export_snapshot()
    bus_snapshot = bus.export_snapshot()
    snapshot: dict[str, Any] = {
        **store_snapshot,
        **bus_snapshot,
        "migration": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    snapshot["counts"] = snapshot_counts(snapshot)
    return snapshot


def import_runtime_snapshot(
    snapshot: dict[str, Any],
    *,
    store: StoreContract,
    bus: InMemoryMessageBus,
    keep_default_agents: bool = False,
) -> dict[str, Any]:
    errors = validate_runtime_snapshot(snapshot)
    if errors:
        raise ValueError("invalid snapshot: " + "; ".join(errors))

    store_counts = store.import_snapshot(snapshot, keep_default_agents=keep_default_agents)
    event_counts = bus.import_snapshot(snapshot)
    imported = {
        **store_counts,
        **event_counts,
    }
    return {
        "counts": imported,
        "snapshot_counts": snapshot_counts(snapshot),
        "matches": imported == snapshot_counts(snapshot),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


