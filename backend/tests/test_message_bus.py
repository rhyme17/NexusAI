from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models.message import BusMessage, MessageType
from backend.app.services import message_bus as message_bus_module
from backend.app.services.message_bus import InMemoryMessageBus


def test_message_bus_respects_configured_history_limit(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_EVENT_HISTORY_MAX", "100")
    bus = InMemoryMessageBus(persistence_enabled=False)

    for idx in range(105):
        bus.publish(
            BusMessage(
                message_id=f"msg_{idx}",
                type=MessageType.TASK_UPDATE,
                sender="test",
                task_id="task_demo",
                payload={"i": idx},
            )
        )

    events, total = bus.list_task_events("task_demo", limit=200)
    assert total == 100
    payload_indexes = [event.payload["i"] for event in events]
    assert payload_indexes[0] == 5
    assert payload_indexes[-1] == 104


def test_message_bus_filters_claim_and_handoff_event_types() -> None:
    bus = InMemoryMessageBus(persistence_enabled=False)
    bus.publish(
        BusMessage(
            message_id="msg_claim",
            type=MessageType.TASK_CLAIM,
            sender="agent_planner",
            task_id="task_demo",
            payload={"agent_id": "agent_planner"},
        )
    )
    bus.publish(
        BusMessage(
            message_id="msg_handoff",
            type=MessageType.TASK_HANDOFF,
            sender="agent_planner",
            receiver="agent_research",
            task_id="task_demo",
            payload={"from_agent_id": "agent_planner", "to_agent_id": "agent_research"},
        )
    )
    bus.publish(
        BusMessage(
            message_id="msg_retry",
            type=MessageType.TASK_RETRY,
            sender="workflow_engine",
            task_id="task_demo",
            payload={"retry_count": 1},
        )
    )

    events, total = bus.list_task_events("task_demo", event_types=[MessageType.TASK_HANDOFF])
    assert total == 1
    assert len(events) == 1
    assert events[0].type == MessageType.TASK_HANDOFF

    retry_events, retry_total = bus.list_task_events("task_demo", event_types=[MessageType.TASK_RETRY])
    assert retry_total == 1
    assert retry_events[0].payload["retry_count"] == 1


def test_message_bus_persists_only_touched_task_histories(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[dict[str, object], tuple[str, ...]]] = []

    def fake_merge_json_object_atomic(path: Path, updates: dict[str, object], *, remove_keys=()) -> None:
        calls.append((dict(updates), tuple(remove_keys)))

    monkeypatch.setattr(message_bus_module, "merge_json_object_atomic", fake_merge_json_object_atomic)

    bus = InMemoryMessageBus(persistence_enabled=True, events_file=tmp_path / "events.json")
    bus.publish(
        BusMessage(
            message_id="msg_task_a_1",
            type=MessageType.TASK_UPDATE,
            sender="test",
            task_id="task_a",
            payload={"i": 1},
        )
    )
    bus.publish(
        BusMessage(
            message_id="msg_task_b_1",
            type=MessageType.TASK_UPDATE,
            sender="test",
            task_id="task_b",
            payload={"i": 2},
        )
    )
    bus.publish(
        BusMessage(
            message_id="msg_task_a_2",
            type=MessageType.TASK_UPDATE,
            sender="test",
            task_id="task_a",
            payload={"i": 3},
        )
    )

    assert [set(update.keys()) for update, _ in calls] == [{"task_a"}, {"task_b"}, {"task_a"}]
    assert all(not remove_keys for _, remove_keys in calls)

    bus.clear_history("task_a")
    assert calls[-1][1] == ("task_a",)


