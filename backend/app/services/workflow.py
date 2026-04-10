from copy import deepcopy
from uuid import uuid4
from datetime import datetime, timezone
from typing import Any

from ..core.config import resolve_decomposition_template
from ..models.message import BusMessage, MessageType
from ..models.task import TaskStatus, TaskStatusUpdate
from .message_bus import InMemoryMessageBus
from .router import TaskRouter
from .store_contract import StoreContract


class WorkflowService:
    """Placeholder workflow entry for future DAG/LangGraph integration."""

    def __init__(self, store: StoreContract, router: TaskRouter, bus: InMemoryMessageBus) -> None:
        self.store = store
        self.router = router
        self.bus = bus

    def enqueue_task(self, task_id: str) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return

        decomposition = task.metadata.get("decomposition") if isinstance(task.metadata, dict) else None
        routing_explanation = task.metadata.get("routing") if isinstance(task.metadata, dict) else None
        if not isinstance(decomposition, dict):
            selected_agents, routing_explanation = self.router.route_task(task, self.store.list_agents())
            decomposition = self._build_decomposition(task.objective, selected_agents, task.metadata)
            task = self.store.assign_workflow_context(
                task_id,
                assigned_agent_ids=selected_agents,
                decomposition=decomposition,
                routing_explanation=routing_explanation,
            ) or task

        subtasks = decomposition.get("subtasks") if isinstance(decomposition.get("subtasks"), list) else []

        self.store.update_task_status(
            task_id,
            TaskStatusUpdate(status=TaskStatus.IN_PROGRESS, progress=5),
        )
        self.publish_events(
            [
                self._build_bus_message(
                    event_type=MessageType.TASK_UPDATE,
                    task_id=task_id,
                    payload={
                        "status": TaskStatus.IN_PROGRESS.value,
                        "progress": 5,
                        "assigned_agent_ids": task.assigned_agent_ids,
                        "subtask_count": len(subtasks),
                        "routing_strategy": routing_explanation.get("strategy") if isinstance(routing_explanation, dict) else None,
                        "routing_reason": routing_explanation.get("reason") if isinstance(routing_explanation, dict) else None,
                    },
                ),
                self._build_bus_message(
                    event_type=MessageType.TASK_PIPELINE_START,
                    task_id=task_id,
                    payload={
                        "workflow_run_id": self._workflow_run_id(decomposition),
                        "node_count": len(self._get_nodes(decomposition)),
                        "ready_queue": list(self._get_ready_queue(decomposition)),
                    },
                ),
            ]
        )
        self.dispatch_ready_nodes(task_id)

    def dispatch_ready_nodes(self, task_id: str, *, limit: int | None = None) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return
        decomposition = self._get_decomposition(task)
        if not decomposition:
            return

        nodes = self._get_nodes(decomposition)
        ready_nodes = [node for node in nodes if node.get("dispatch_state") == "ready"]
        if not ready_nodes:
            return

        active_owner = task.current_agent_id
        dispatched = 0
        events: list[BusMessage] = []
        for node in ready_nodes[: limit or len(ready_nodes)]:
            assigned_agent_id = self._normalize_string(node.get("assigned_agent_id"))
            if assigned_agent_id:
                if not active_owner:
                    claimed = self.store.claim_task(task_id, assigned_agent_id)
                    if claimed:
                        task = claimed
                    events.append(
                        self._build_bus_message(
                            event_type=MessageType.TASK_CLAIM,
                            task_id=task_id,
                            sender=assigned_agent_id,
                            payload={"agent_id": assigned_agent_id, "note": "workflow dispatch"},
                        )
                    )
                elif active_owner != assigned_agent_id:
                    handed_off = self.store.handoff_task(task_id, active_owner, assigned_agent_id, "workflow dispatch")
                    if handed_off:
                        task = handed_off
                    events.append(
                        self._build_bus_message(
                            event_type=MessageType.TASK_HANDOFF,
                            task_id=task_id,
                            sender=active_owner,
                            receiver=assigned_agent_id,
                            payload={
                                "from_agent_id": active_owner,
                                "to_agent_id": assigned_agent_id,
                                "reason": "workflow dispatch",
                                "node_id": node.get("node_id"),
                            },
                        )
                    )
                active_owner = assigned_agent_id

            node["status"] = "in_progress"
            node["dispatch_state"] = "running"
            node["started_at"] = self._timestamp()
            node["attempt_count"] = int(node.get("attempt_count") or 0) + 1
            dispatched += 1
            events.append(
                self._build_bus_message(
                    event_type=MessageType.TASK_UPDATE,
                    task_id=task_id,
                    payload={
                        "workflow_event": "node_dispatched",
                        "node_id": node.get("node_id"),
                        "assigned_agent_id": assigned_agent_id,
                        "attempt_count": node.get("attempt_count"),
                    },
                )
            )

        self._refresh_dispatch_state(decomposition)
        self.store.update_workflow_decomposition(task_id, decomposition)
        if dispatched:
            events.append(
                self._build_bus_message(
                    event_type=MessageType.TASK_UPDATE,
                    task_id=task_id,
                    payload={
                        "workflow_event": "queue_dispatch",
                        "ready_queue": list(self._get_ready_queue(decomposition)),
                        "dispatch_state": deepcopy(self._get_dispatch_state(decomposition)),
                    },
                )
            )
            self.publish_events(events)

    def complete_node(self, task_id: str, *, node_id: str | None = None, result: dict[str, Any] | None = None) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return
        decomposition = self._get_decomposition(task)
        if not decomposition:
            return

        node = self._find_target_node(decomposition, node_id=node_id, state="running")
        if node is None:
            return

        node["status"] = "completed"
        node["dispatch_state"] = "completed"
        node["completed_at"] = self._timestamp()
        if result is not None:
            node["last_result"] = result

        for candidate in self._get_nodes(decomposition):
            if candidate.get("dispatch_state") != "blocked":
                continue
            depends_on = [str(item) for item in candidate.get("depends_on", []) if str(item)]
            if depends_on and all(self._node_is_completed(decomposition, dependency) for dependency in depends_on):
                candidate["dispatch_state"] = "ready"

        self._refresh_dispatch_state(decomposition)
        self.store.update_workflow_decomposition(task_id, decomposition)
        self.publish_event(
            event_type=MessageType.TASK_UPDATE,
            task_id=task_id,
            payload={
                "workflow_event": "node_completed",
                "node_id": node.get("node_id"),
                "ready_queue": list(self._get_ready_queue(decomposition)),
                "dispatch_state": deepcopy(self._get_dispatch_state(decomposition)),
            },
        )

        if self._all_nodes_completed(decomposition):
            self.publish_event(
                event_type=MessageType.TASK_PIPELINE_FINISH,
                task_id=task_id,
                payload={
                    "workflow_run_id": self._workflow_run_id(decomposition),
                    "completed_count": self._get_dispatch_state(decomposition).get("completed_count", 0),
                },
            )
            return

        self.dispatch_ready_nodes(task_id)

    def fail_node(
        self,
        task_id: str,
        *,
        node_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return
        decomposition = self._get_decomposition(task)
        if not decomposition:
            return

        node = self._find_target_node(decomposition, node_id=node_id, state="running")
        if node is None:
            return

        node["status"] = "failed"
        node["dispatch_state"] = "failed"
        node["failed_at"] = self._timestamp()
        node["last_error_code"] = error_code
        node["last_error_message"] = error_message
        failure_policy = self._failure_policy(decomposition)
        if failure_policy == "continue":
            for candidate in self._get_nodes(decomposition):
                if candidate.get("dispatch_state") != "blocked":
                    continue
                depends_on = [str(item) for item in candidate.get("depends_on", []) if str(item)]
                if depends_on and all(self._node_is_terminal(decomposition, dependency) for dependency in depends_on):
                    candidate["dispatch_state"] = "ready"
        self._refresh_dispatch_state(decomposition)
        self.store.update_workflow_decomposition(task_id, decomposition)
        self.publish_event(
            event_type=MessageType.TASK_UPDATE,
            task_id=task_id,
            payload={
                "workflow_event": "node_failed",
                "node_id": node.get("node_id"),
                "error_code": error_code,
                "error_message": error_message,
                "failure_policy": failure_policy,
                "dispatch_state": deepcopy(self._get_dispatch_state(decomposition)),
            },
        )
        if failure_policy == "continue":
            self.dispatch_ready_nodes(task_id)

    def requeue_task(self, task_id: str, *, reason: str | None = None, force: bool = False) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return
        decomposition = self._get_decomposition(task)
        if not decomposition:
            self.enqueue_task(task_id)
            return

        nodes = self._get_nodes(decomposition)
        has_failed_node = any(node.get("dispatch_state") == "failed" or node.get("status") == "failed" for node in nodes)
        if not force and not has_failed_node:
            self.publish_event(
                event_type=MessageType.TASK_UPDATE,
                task_id=task_id,
                payload={
                    "workflow_event": "task_requeue_skipped",
                    "reason": reason,
                    "ready_queue": list(self._get_ready_queue(decomposition)),
                    "dispatch_state": deepcopy(self._get_dispatch_state(decomposition)),
                },
            )
            return

        for node in nodes:
            node.pop("started_at", None)
            node.pop("completed_at", None)
            node.pop("failed_at", None)
            node.pop("last_result", None)
            node.pop("last_error_code", None)
            node.pop("last_error_message", None)
            depends_on = [str(item) for item in node.get("depends_on", []) if str(item)]
            node["status"] = "queued"
            node["dispatch_state"] = "ready" if not depends_on else "blocked"
        self._refresh_dispatch_state(decomposition)
        self.store.update_workflow_decomposition(task_id, decomposition)
        self.store.update_task_status(task_id, TaskStatusUpdate(status=TaskStatus.IN_PROGRESS, progress=5))
        self.publish_event(
            event_type=MessageType.TASK_UPDATE,
            task_id=task_id,
            payload={
                "workflow_event": "task_requeued",
                "reason": reason,
                "ready_queue": list(self._get_ready_queue(decomposition)),
                "dispatch_state": deepcopy(self._get_dispatch_state(decomposition)),
            },
        )
        self.dispatch_ready_nodes(task_id)

    def _build_decomposition(
        self,
        objective: str,
        assigned_agent_ids: list[str],
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        template_name, phases, matched_keywords = resolve_decomposition_template(metadata, objective)
        use_parallel_branches = bool(metadata.get("workflow_parallel_branches")) if isinstance(metadata, dict) else False
        failure_policy = self._normalize_failure_policy(metadata.get("workflow_failure_policy") if isinstance(metadata, dict) else None)
        subtasks: list[dict[str, object]] = []
        dag_nodes: list[dict[str, object]] = []
        dag_edges: list[dict[str, object]] = []

        def resolve_dependencies(step_index: int, total_steps: int) -> list[str]:
            if not use_parallel_branches or total_steps < 4:
                return [f"step_{step_index - 1}"] if step_index > 1 else []
            if step_index == 1:
                return []
            if step_index in {2, 3}:
                return ["step_1"]
            if step_index == total_steps:
                return ["step_2", "step_3"]
            return [f"step_{step_index - 1}"]

        for index, title in enumerate(phases, start=1):
            node_id = f"step_{index}"
            assigned_agent_id = assigned_agent_ids[(index - 1) % len(assigned_agent_ids)] if assigned_agent_ids else None
            depends_on = resolve_dependencies(index, len(phases))
            subtasks.append(
                {
                    "step_id": node_id,
                    "title": title,
                    "status": "queued",
                    "assigned_agent_id": assigned_agent_id,
                    "depends_on": depends_on,
                }
            )
            dag_nodes.append(
                {
                    "node_id": node_id,
                    "title": title,
                    "status": "queued",
                    "assigned_agent_id": assigned_agent_id,
                    "depends_on": depends_on,
                    "sequence": index,
                    "dispatch_state": "ready" if not depends_on else "blocked",
                }
            )
            if index > 1:
                for from_node in depends_on:
                    dag_edges.append(
                        {
                            "edge_id": f"edge_{from_node}_{node_id}",
                            "from_node_id": from_node,
                            "to_node_id": node_id,
                        }
                    )

        workflow_run_id = f"wf_{uuid4().hex[:10]}"
        ready_queue = [node["node_id"] for node in dag_nodes if node["dispatch_state"] == "ready"]
        return {
            "mode": "mvp_linear",
            "parallel_branches_enabled": use_parallel_branches,
            "failure_policy": failure_policy,
            "template": template_name,
            "matched_keywords": matched_keywords,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "objective_snapshot": objective,
            "workflow_run": {
                "workflow_run_id": workflow_run_id,
                "queue_backend": "in_process",
                "scheduler_mode": "mvp_linear_queue",
                "node_count": len(dag_nodes),
                "edge_count": len(dag_edges),
            },
            "dag_nodes": dag_nodes,
            "dag_edges": dag_edges,
            "ready_queue": ready_queue,
            "dispatch_state": {
                "pending_count": len(dag_nodes),
                "ready_count": len(ready_queue),
                "blocked_count": max(len(dag_nodes) - len(ready_queue), 0),
                "running_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "last_transition_at": datetime.now(timezone.utc).isoformat(),
            },
            "subtasks": subtasks,
        }

    def _get_decomposition(self, task: object) -> dict[str, Any] | None:
        metadata = getattr(task, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        decomposition = metadata.get("decomposition")
        if not isinstance(decomposition, dict):
            return None
        return deepcopy(decomposition)

    @staticmethod
    def _get_nodes(decomposition: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = decomposition.get("dag_nodes")
        if not isinstance(nodes, list):
            return []
        return [node for node in nodes if isinstance(node, dict)]

    @staticmethod
    def _get_dispatch_state(decomposition: dict[str, Any]) -> dict[str, Any]:
        dispatch_state = decomposition.get("dispatch_state")
        if not isinstance(dispatch_state, dict):
            dispatch_state = {}
            decomposition["dispatch_state"] = dispatch_state
        return dispatch_state

    @staticmethod
    def _workflow_run_id(decomposition: dict[str, Any]) -> str | None:
        workflow_run = decomposition.get("workflow_run")
        if isinstance(workflow_run, dict):
            run_id = workflow_run.get("workflow_run_id")
            if isinstance(run_id, str):
                return run_id
        return None

    def _refresh_dispatch_state(self, decomposition: dict[str, Any]) -> None:
        nodes = self._get_nodes(decomposition)
        ready_queue = [str(node.get("node_id")) for node in nodes if node.get("dispatch_state") == "ready"]
        decomposition["ready_queue"] = ready_queue
        dispatch_state = self._get_dispatch_state(decomposition)
        dispatch_state["pending_count"] = len(nodes)
        dispatch_state["ready_count"] = len(ready_queue)
        dispatch_state["blocked_count"] = len([node for node in nodes if node.get("dispatch_state") == "blocked"])
        dispatch_state["running_count"] = len([node for node in nodes if node.get("dispatch_state") == "running"])
        dispatch_state["completed_count"] = len([node for node in nodes if node.get("dispatch_state") == "completed"])
        dispatch_state["failed_count"] = len([node for node in nodes if node.get("dispatch_state") == "failed"])
        dispatch_state["last_transition_at"] = self._timestamp()

    @staticmethod
    def _get_ready_queue(decomposition: dict[str, Any]) -> list[str]:
        ready_queue = decomposition.get("ready_queue")
        if not isinstance(ready_queue, list):
            return []
        return [str(item) for item in ready_queue if str(item)]

    def _find_target_node(
        self,
        decomposition: dict[str, Any],
        *,
        node_id: str | None,
        state: str,
    ) -> dict[str, Any] | None:
        nodes = self._get_nodes(decomposition)
        if node_id:
            for node in nodes:
                if node.get("node_id") == node_id and node.get("dispatch_state") == state:
                    return node
        for node in nodes:
            if node.get("dispatch_state") == state:
                return node
        return None

    def _node_is_completed(self, decomposition: dict[str, Any], node_id: str) -> bool:
        for node in self._get_nodes(decomposition):
            if node.get("node_id") == node_id:
                return node.get("dispatch_state") == "completed"
        return False

    def _node_is_terminal(self, decomposition: dict[str, Any], node_id: str) -> bool:
        for node in self._get_nodes(decomposition):
            if node.get("node_id") == node_id:
                return node.get("dispatch_state") in {"completed", "failed"}
        return False

    def _failure_policy(self, decomposition: dict[str, Any]) -> str:
        return self._normalize_failure_policy(decomposition.get("failure_policy"))

    @staticmethod
    def _normalize_failure_policy(value: object) -> str:
        if isinstance(value, str) and value.strip().lower() in {"fail_fast", "continue"}:
            return value.strip().lower()
        return "fail_fast"

    def _all_nodes_completed(self, decomposition: dict[str, Any]) -> bool:
        nodes = self._get_nodes(decomposition)
        return bool(nodes) and all(node.get("dispatch_state") == "completed" for node in nodes)

    @staticmethod
    def _normalize_string(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def publish_event(self, *, event_type: MessageType, task_id: str, payload: dict[str, object], sender: str = "workflow_engine", receiver: str | None = None) -> None:
        self.bus.publish(self._build_bus_message(event_type=event_type, task_id=task_id, payload=payload, sender=sender, receiver=receiver))

    def publish_events(self, events: list[BusMessage]) -> None:
        self.bus.publish_many(events)

    @staticmethod
    def _build_bus_message(
        *,
        event_type: MessageType,
        task_id: str,
        payload: dict[str, object],
        sender: str = "workflow_engine",
        receiver: str | None = None,
    ) -> BusMessage:
        return BusMessage(
            message_id=f"msg_{uuid4().hex[:8]}",
            type=event_type,
            sender=sender,
            receiver=receiver,
            task_id=task_id,
            payload=payload,
        )

