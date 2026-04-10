from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.core import config
from backend.app.core.startup import apply_startup_clear_if_enabled
from backend.app.models.message import BusMessage, MessageType
from backend.app.services import store as store_service
from backend.app.models.task import TaskCreate, TaskPriority
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.store import InMemoryStore


def test_load_env_files_reads_configured_env_file(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "NEXUSAI_API_AUTH_ENABLED=true\nNEXUSAI_DEBUG_API_ENABLED=true\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("NEXUSAI_ENV_FILE", str(env_file))
    monkeypatch.delenv("NEXUSAI_API_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("NEXUSAI_DEBUG_API_ENABLED", raising=False)
    monkeypatch.setattr(config, "_ENV_LOADED", False)

    config.load_env_files()

    assert config.is_api_auth_enabled() is True
    assert config.is_debug_api_enabled() is True


def test_apply_startup_clear_if_enabled_clears_tasks_and_events(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_CLEAR_ON_STARTUP", "true")
    monkeypatch.setenv("NEXUSAI_CLEAR_EVENTS_ONLY_ON_STARTUP", "false")
    monkeypatch.setenv("NEXUSAI_CLEAR_RESTORE_SEED_ON_STARTUP", "false")

    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    task = store.create_task(TaskCreate(objective="clear startup", priority=TaskPriority.LOW))
    bus.publish(
        BusMessage(
            message_id="msg_startup_clear",
            type=MessageType.TASK_REQUEST,
            sender="api_gateway",
            task_id=task.task_id,
            payload={"objective": "clear startup"},
        )
    )

    result = apply_startup_clear_if_enabled(store=store, bus=bus)

    assert result == {"cleared": True, "events_only": False, "seed_restored": False}
    assert store.list_tasks() == []
    exported = bus.export_snapshot()
    assert exported["events"] == {}


def test_apply_startup_clear_events_only(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_CLEAR_ON_STARTUP", "true")
    monkeypatch.setenv("NEXUSAI_CLEAR_EVENTS_ONLY_ON_STARTUP", "true")
    monkeypatch.setenv("NEXUSAI_CLEAR_RESTORE_SEED_ON_STARTUP", "false")

    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    task = store.create_task(TaskCreate(objective="events only", priority=TaskPriority.LOW))
    bus.publish(
        BusMessage(
            message_id="msg_events_only",
            type=MessageType.TASK_REQUEST,
            sender="api_gateway",
            task_id=task.task_id,
            payload={"objective": "events only"},
        )
    )

    result = apply_startup_clear_if_enabled(store=store, bus=bus)

    assert result == {"cleared": True, "events_only": True, "seed_restored": False}
    assert store.get_task(task.task_id) is not None
    assert bus.export_snapshot()["events"] == {}


def test_api_key_roles_merge_with_keys_and_default_role(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_KEYS", "plain-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "admin-key:admin,operator-key:operator,bad-key:invalid,implicit-key")
    monkeypatch.setenv("NEXUSAI_API_AUTH_DEFAULT_ROLE", "viewer")

    keys = config.get_api_auth_keys()

    assert {"plain-key", "admin-key", "operator-key", "bad-key", "implicit-key"}.issubset(keys)
    assert config.resolve_api_key_role("admin-key") == "admin"
    assert config.resolve_api_key_role("operator-key") == "operator"
    assert config.resolve_api_key_role("plain-key") == "viewer"
    assert config.resolve_api_key_role("bad-key") == "viewer"
    assert config.resolve_api_key_role("missing-key") is None


def test_postgres_store_init_failure_falls_back_to_json_backend(monkeypatch) -> None:
    class FailingPostgresStore:
        def __init__(self, **_: object) -> None:
            raise RuntimeError("postgres unavailable")

    monkeypatch.setenv("NEXUSAI_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("NEXUSAI_STORAGE_FALLBACK_ON_ERROR", "true")
    monkeypatch.setenv("NEXUSAI_STORAGE_FALLBACK_BACKEND", "json")
    monkeypatch.setattr(store_service, "PostgresStore", FailingPostgresStore)
    monkeypatch.setattr(store_service, "_store", None)
    monkeypatch.setattr(store_service, "_store_signature", None)

    resolved = store_service.get_store()

    assert isinstance(resolved, InMemoryStore)


def test_postgres_store_init_failure_raises_when_fallback_disabled(monkeypatch) -> None:
    class FailingPostgresStore:
        def __init__(self, **_: object) -> None:
            raise RuntimeError("postgres unavailable")

    monkeypatch.setenv("NEXUSAI_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("NEXUSAI_STORAGE_FALLBACK_ON_ERROR", "false")
    monkeypatch.setattr(store_service, "PostgresStore", FailingPostgresStore)
    monkeypatch.setattr(store_service, "_store", None)
    monkeypatch.setattr(store_service, "_store_signature", None)

    with pytest.raises(RuntimeError, match="postgres unavailable"):
        store_service.get_store()


def test_resolve_router_policy_uses_defaults_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("NEXUSAI_ROUTER_SKILL_WEIGHT", raising=False)
    monkeypatch.delenv("NEXUSAI_ROUTER_STATUS_WEIGHT", raising=False)
    monkeypatch.delenv("NEXUSAI_ROUTER_LOAD_PENALTY", raising=False)

    policy = config.resolve_router_policy()

    assert policy["skill_weight"] == 100
    assert policy["status_weight"] == 10
    assert policy["load_penalty"] == 1
    assert policy["priority_status_bonus"]["high"] == 6


def test_resolve_router_policy_supports_env_and_metadata_override(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_ROUTER_SKILL_WEIGHT", "120")
    monkeypatch.setenv("NEXUSAI_ROUTER_STATUS_WEIGHT", "15")
    monkeypatch.setenv("NEXUSAI_ROUTER_LOAD_PENALTY", "invalid")
    monkeypatch.setenv("NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_HIGH", "9")

    policy = config.resolve_router_policy(
        {
            "routing_policy": {
                "status_weight": 20,
                "priority_status_bonus": {"high": 12},
            }
        }
    )

    assert policy["skill_weight"] == 120
    assert policy["status_weight"] == 20
    assert policy["load_penalty"] == 1
    assert policy["priority_status_bonus"]["high"] == 12


