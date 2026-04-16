from datetime import datetime
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from ..core.config import is_api_auth_enabled, resolve_max_retries
from ..models.message import BusMessage, MessageType, TaskEventsResponse
from ..models.task import (
    Task,
    TaskAttemptsResponse,
    TaskClaimRequest,
    TaskConsensusResponse,
    TaskCreate,
    TaskExecutionPreviewResponse,
    TaskExecutionRequest,
    TaskHandoffRequest,
    TaskResultResponse,
    TaskRetryRequest,
    TaskSimulationRequest,
    TaskStatusUpdate,
)
from ..services.agent_execution import AgentExecutionService, get_agent_execution_service
from ..services.consensus import ConsensusService
from ..services.message_bus import InMemoryMessageBus, get_message_bus
from ..services.router import TaskRouter
from ..services.store import get_store
from ..services.store_contract import StoreContract
from ..services.task_execution_coordinator import TaskExecutionCoordinator
from ..services.task_status_service import TaskStatusService
from ..services.workflow import WorkflowService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _request_user(request: Request):
    return getattr(request.state, "auth_user", None)


def _request_is_admin(request: Request) -> bool:
    return getattr(request.state, "auth_role", None) == "admin" and _request_user(request) is not None


def _get_visible_task_or_404(*, request: Request, store: StoreContract, task_id: str) -> Task:
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user = _request_user(request)
    if _request_is_admin(request):
        return task
    if user is None:
        if is_api_auth_enabled():
            # API-key-only callers must not gain blanket task visibility.
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    if task.owner_user_id != user.user_id:
        # Hide task existence for non-owners.
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def get_workflow(
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> WorkflowService:
    return WorkflowService(store=store, router=TaskRouter(), bus=bus)


def get_consensus_service() -> ConsensusService:
    return ConsensusService()


def get_execution_service() -> AgentExecutionService:
    return get_agent_execution_service()


def get_task_status_service(
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> TaskStatusService:
    return TaskStatusService(store=store, bus=bus)


def get_execution_coordinator(
    store: StoreContract = Depends(get_store),
    task_status_service: TaskStatusService = Depends(get_task_status_service),
    consensus_service: ConsensusService = Depends(get_consensus_service),
    execution_service: AgentExecutionService = Depends(get_execution_service),
) -> TaskExecutionCoordinator:
    return TaskExecutionCoordinator(
        store=store,
        status_service=task_status_service,
        consensus_service=consensus_service,
        execution_service=execution_service,
    )


@router.post("", response_model=Task, status_code=status.HTTP_201_CREATED, summary="Create Task")
def create_task(
    request: Request,
    payload: TaskCreate,
    store: StoreContract = Depends(get_store),
    workflow: WorkflowService = Depends(get_workflow),
    status_service: TaskStatusService = Depends(get_task_status_service),
) -> Task:
    user = _request_user(request)
    task = store.create_task(
        payload,
        owner_user_id=user.user_id if user else None,
        owner_username=user.username if user else None,
    )
    status_service.publish_event(
        event_type=MessageType.TASK_REQUEST,
        task_id=task.task_id,
        sender="api_gateway",
        payload={"objective": task.objective, "priority": task.priority.value},
    )
    workflow.enqueue_task(task.task_id)
    return store.get_task(task.task_id) or task


@router.get("/{task_id}", response_model=Task, summary="Get Task")
def get_task(task_id: str, request: Request, store: StoreContract = Depends(get_store)) -> Task:
    return _get_visible_task_or_404(request=request, store=store, task_id=task_id)


@router.get("/{task_id}/events", response_model=list[BusMessage] | TaskEventsResponse)
def get_task_events(
    request: Request,
    task_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    sort: Literal["asc", "desc"] = Query(default="asc"),
    include_meta: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    type: list[MessageType] | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> list[BusMessage] | TaskEventsResponse:
    _get_visible_task_or_404(request=request, store=store, task_id=task_id)
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        raise HTTPException(status_code=422, detail="Invalid time range: 'from' must be before or equal to 'to'")

    effective_offset = offset
    if cursor is not None:
        try:
            parsed_cursor = int(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid cursor: must be a non-negative integer string") from exc
        if parsed_cursor < 0:
            raise HTTPException(status_code=422, detail="Invalid cursor: must be a non-negative integer string")
        effective_offset = parsed_cursor

    events, total_count = bus.list_task_events(
        task_id,
        offset=effective_offset,
        limit=limit,
        event_types=type,
        from_time=from_ts,
        to_time=to_ts,
        sort=sort,
    )
    response.headers["X-Total-Count"] = str(total_count)
    if include_meta:
        next_offset = effective_offset + len(events)
        has_more = next_offset < total_count
        return TaskEventsResponse(
            total_count=total_count,
            offset=effective_offset,
            limit=limit,
            sort=sort,
            has_more=has_more,
            next_cursor=str(next_offset) if has_more else None,
            items=events,
        )
    return events


@router.patch("/{task_id}/status", response_model=Task)
def update_task_status(
    request: Request,
    task_id: str,
    payload: TaskStatusUpdate,
    consensus_service: ConsensusService = Depends(get_consensus_service),
    status_service: TaskStatusService = Depends(get_task_status_service),
) -> Task:
    _get_visible_task_or_404(request=request, store=status_service.store, task_id=task_id)
    return status_service.apply_status_update(task_id, payload, consensus_service)


@router.post("/{task_id}/claim", response_model=Task)
def claim_task(
    request: Request,
    task_id: str,
    payload: TaskClaimRequest,
    status_service: TaskStatusService = Depends(get_task_status_service),
) -> Task:
    _get_visible_task_or_404(request=request, store=status_service.store, task_id=task_id)
    return status_service.claim_task(task_id=task_id, agent_id=payload.agent_id, note=payload.note)


@router.post("/{task_id}/handoff", response_model=Task)
def handoff_task(
    request: Request,
    task_id: str,
    payload: TaskHandoffRequest,
    status_service: TaskStatusService = Depends(get_task_status_service),
) -> Task:
    _get_visible_task_or_404(request=request, store=status_service.store, task_id=task_id)
    return status_service.handoff_task(
        task_id=task_id,
        from_agent_id=payload.from_agent_id,
        to_agent_id=payload.to_agent_id,
        reason=payload.reason,
    )


@router.post("/{task_id}/simulate", response_model=Task)
def simulate_task_execution(
    request: Request,
    task_id: str,
    payload: TaskSimulationRequest,
    coordinator: TaskExecutionCoordinator = Depends(get_execution_coordinator),
) -> Task:
    _get_visible_task_or_404(request=request, store=coordinator.store, task_id=task_id)
    return coordinator.simulate_task_execution(task_id=task_id, payload=payload)


@router.post("/{task_id}/execute/preview", response_model=TaskExecutionPreviewResponse)
def preview_execute_task(
    request: Request,
    task_id: str,
    payload: TaskExecutionRequest,
    coordinator: TaskExecutionCoordinator = Depends(get_execution_coordinator),
) -> TaskExecutionPreviewResponse:
    _get_visible_task_or_404(request=request, store=coordinator.store, task_id=task_id)
    return coordinator.preview_execute(task_id=task_id, payload=payload)


@router.post("/{task_id}/execute", response_model=Task, summary="Execute Task")
def execute_task(
    request: Request,
    task_id: str,
    payload: TaskExecutionRequest,
    coordinator: TaskExecutionCoordinator = Depends(get_execution_coordinator),
) -> Task:
    _get_visible_task_or_404(request=request, store=coordinator.store, task_id=task_id)
    return coordinator.execute_task(task_id=task_id, payload=payload)


@router.post("/{task_id}/retry", response_model=Task, summary="Retry Task")
def retry_task(
    request: Request,
    task_id: str,
    payload: TaskRetryRequest,
    workflow: WorkflowService = Depends(get_workflow),
    coordinator: TaskExecutionCoordinator = Depends(get_execution_coordinator),
) -> Task:
    _get_visible_task_or_404(request=request, store=coordinator.store, task_id=task_id)
    return coordinator.retry_task(task_id=task_id, payload=payload, workflow=workflow)


@router.get("/{task_id}/attempts", response_model=TaskAttemptsResponse)
def get_task_attempts(
    request: Request,
    task_id: str,
    store: StoreContract = Depends(get_store),
) -> TaskAttemptsResponse:
    task = _get_visible_task_or_404(request=request, store=store, task_id=task_id)
    return TaskAttemptsResponse(
        task_id=task.task_id,
        retry_count=task.retry_count,
        max_retries=resolve_max_retries(task.metadata),
        items=task.attempt_history,
    )


@router.get("/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(
    request: Request,
    task_id: str,
    store: StoreContract = Depends(get_store),
) -> TaskResultResponse:
    _get_visible_task_or_404(request=request, store=store, task_id=task_id)
    task_result = store.get_task_result(task_id)
    if not task_result:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_result


@router.get("/{task_id}/result/export", summary="Export task result")
def export_task_result(
    request: Request,
    task_id: str,
    format: Literal["md", "txt"] = Query(default="md"),
    store: StoreContract = Depends(get_store),
) -> Response:
    task = _get_visible_task_or_404(request=request, store=store, task_id=task_id)

    content = _render_task_result_export(task, format)
    extension = "md" if format == "md" else "txt"
    media_type = "text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8"
    filename = _build_export_filename(task.objective, task_id, extension)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{task_id}/consensus", response_model=TaskConsensusResponse)
def get_task_consensus(
    request: Request,
    task_id: str,
    store: StoreContract = Depends(get_store),
) -> TaskConsensusResponse:
    task = _get_visible_task_or_404(request=request, store=store, task_id=task_id)
    return TaskConsensusResponse(
        task_id=task.task_id,
        consensus=task.consensus,
        proposals=task.proposals,
    )


@router.delete("/me", summary="Delete Current User Tasks")
def delete_my_tasks(
    request: Request,
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> dict[str, object]:
    user = _request_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "E_AUTH_UNAUTHORIZED",
                "user_message": "请先登录。",
                "detail": "Login required for deleting owned tasks",
            },
        )
    owned_task_ids = [task.task_id for task in store.list_tasks() if task.owner_user_id == user.user_id]
    deleted_count = store.delete_tasks_by_owner(user.user_id)
    for task_id in owned_task_ids:
        bus.clear_history(task_id)
    return {"status": "deleted", "deleted_count": deleted_count}


@router.delete("/{task_id}", summary="Delete Task")
def delete_task(
    task_id: str,
    request: Request,
    store: StoreContract = Depends(get_store),
    bus: InMemoryMessageBus = Depends(get_message_bus),
) -> dict[str, str]:
    _get_visible_task_or_404(request=request, store=store, task_id=task_id)
    deleted = store.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    bus.clear_history(task_id)
    return {"status": "deleted", "task_id": task_id}


@router.get("", response_model=list[Task], summary="List Tasks")
def list_tasks(request: Request, store: StoreContract = Depends(get_store)) -> list[Task]:
    user = _request_user(request)
    tasks = store.list_tasks()
    if _request_is_admin(request):
        return tasks
    if user is None:
        if is_api_auth_enabled():
            # Keep API-key-only callers from seeing tasks they do not own.
            return []
        return tasks
    return [task for task in tasks if task.owner_user_id == user.user_id]


def _render_task_result_export(task: Task, format: Literal["md", "txt"]) -> str:
    result = task.result if isinstance(task.result, dict) else {}
    
    content_keys = ["final_output", "output", "report", "document", "content", "text", "summary"]
    summary = ""
    for key in content_keys:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            summary = value.strip()
            break
    
    if not summary and result:
        try:
            summary = json.dumps(result, ensure_ascii=False, indent=2)
        except Exception:
            summary = str(result)
    
    if not summary:
        summary = "No result output yet." if format == "txt" else "暂无结果输出。"

    if format == "txt":
        return (
            f"Task ID: {task.task_id}\n"
            f"Objective: {task.objective}\n"
            f"Status: {task.status.value}\n"
            f"Updated At: {task.updated_at.isoformat()}\n\n"
            f"Result\n{'-' * 40}\n"
            f"{summary}\n"
        )

    return (
        f"# {task.objective}\n\n"
        f"- Task ID: `{task.task_id}`\n"
        f"- Status: `{task.status.value}`\n"
        f"- Updated At: `{task.updated_at.isoformat()}`\n\n"
        "## Result\n\n"
        f"{summary}\n"
    )


def _build_export_filename(objective: str, task_id: str, extension: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", objective.lower()).strip("-")
    if not normalized:
        normalized = task_id
    return f"{normalized[:48]}-{task_id}.{extension}"

