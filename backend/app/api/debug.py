from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.config import is_debug_api_enabled
from ..core.security import ensure_request_role
from ..services.message_bus import InMemoryMessageBus, get_message_bus
from ..services.store import get_store
from ..services.store_contract import StoreContract

router = APIRouter(prefix="/api/debug/storage", tags=["debug"])


def _ensure_debug_api_enabled() -> None:
    if not is_debug_api_enabled():
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/export")
def export_storage_snapshot(
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> dict[str, object]:
    _ensure_debug_api_enabled()
    store_snapshot = store.export_snapshot()
    bus_snapshot = bus.export_snapshot()
    tasks_snapshot = cast(dict[str, Any], store_snapshot.get("tasks", {}))
    agents_snapshot = cast(dict[str, Any], store_snapshot.get("agents", {}))
    return {
        "counts": {
            "tasks": len(tasks_snapshot),
            "agents": len(agents_snapshot),
            "tasks_with_events": len(bus_snapshot["events"]),
            "events": sum(len(items) for items in bus_snapshot["events"].values()),
        },
        **store_snapshot,
        **bus_snapshot,
    }


@router.post("/clear")
def clear_storage_snapshot(
    request: Request,
    keep_default_agents: bool = Query(default=True),
    clear_events_only: bool = Query(default=False),
    restore_seed: bool = Query(default=False),
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> dict[str, object]:
    _ensure_debug_api_enabled()
    ensure_request_role(request, allowed_roles={"admin"})
    if clear_events_only and restore_seed:
        raise HTTPException(status_code=422, detail="restore_seed cannot be used with clear_events_only=true")

    seed_restored = False
    if clear_events_only:
        bus.clear_history()
    else:
        store.clear(keep_default_agents=keep_default_agents)
        bus.clear_history()
        if restore_seed:
            seed_restored = store.apply_seed_data()

    store_snapshot = store.export_snapshot()
    bus_snapshot = bus.export_snapshot()
    tasks_snapshot = cast(dict[str, Any], store_snapshot.get("tasks", {}))
    agents_snapshot = cast(dict[str, Any], store_snapshot.get("agents", {}))
    return {
        "status": "cleared",
        "seed_restored": seed_restored,
        "counts": {
            "tasks": len(tasks_snapshot),
            "agents": len(agents_snapshot),
            "tasks_with_events": len(bus_snapshot["events"]),
            "events": sum(len(items) for items in bus_snapshot["events"].values()),
        },
    }


