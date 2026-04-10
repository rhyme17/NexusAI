from __future__ import annotations

from typing import Any

from .config import clear_events_only_on_startup, restore_seed_on_startup, should_clear_on_startup


def apply_startup_clear_if_enabled(*, store: Any, bus: Any) -> dict[str, bool] | None:
    if not should_clear_on_startup():
        return None

    events_only = clear_events_only_on_startup()
    restore_seed = restore_seed_on_startup()
    if events_only and restore_seed:
        # restore_seed requires full clear; events-only takes precedence for safety.
        restore_seed = False

    seed_restored = False
    if events_only:
        bus.clear_history()
    else:
        store.clear(keep_default_agents=True)
        bus.clear_history()
        if restore_seed and hasattr(store, "apply_seed_data"):
            seed_restored = bool(store.apply_seed_data())

    return {
        "cleared": True,
        "events_only": events_only,
        "seed_restored": seed_restored,
    }

