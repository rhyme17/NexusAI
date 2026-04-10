from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models.message import BusMessage, MessageType


def test_message_type_covers_mvp_and_prospectus_core_events() -> None:
    required_event_types = {
        "TaskRequest",
        "TaskClaim",
        "TaskUpdate",
        "TaskResult",
        "TaskHandoff",
        "TaskReject",
        "ConflictNotice",
        "Vote",
        "Decision",
        "TaskComplete",
    }
    actual_event_types = {event.value for event in MessageType}
    assert required_event_types.issubset(actual_event_types)


def test_bus_message_keeps_stable_contract_shape() -> None:
    message = BusMessage(
        message_id="msg_contract",
        type=MessageType.TASK_UPDATE,
        sender="workflow_engine",
        receiver="agent_research",
        task_id="task_contract",
        payload={"status": "in_progress"},
        metadata={"confidence": 0.9},
    )

    dumped = message.model_dump(mode="json")
    assert set(dumped.keys()) == {
        "message_id",
        "type",
        "sender",
        "receiver",
        "task_id",
        "payload",
        "metadata",
        "timestamp",
    }
    assert dumped["type"] == "TaskUpdate"

