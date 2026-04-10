# NexusAI 协议说明（MVP）

本文档描述当前 `NexusAI` 代码中已经实际使用的任务、事件、错误与执行协议。

---

## 1. 任务生命周期

当前任务状态：

- `queued`
- `in_progress`
- `completed`
- `failed`

### 当前允许的状态流转

- `queued -> in_progress`
- `queued -> completed`（MVP 快捷路径，便于手动推进与演示）
- `queued -> failed`
- `in_progress -> completed`
- `in_progress -> failed`
- 同状态幂等更新允许（例如 `completed -> completed`）

### 当前不允许的流转

- `failed -> in_progress`（必须先调用 `/retry`）
- `completed -> failed`
- 任意终态直接回滚到非终态

---

## 2. 认领 / 交接规则

### 认领（Claim）

- 任务可被智能体 claim，成为当前 owner
- 已完成任务不能再 claim
- 若任务已经被其他智能体占用，则 claim 返回冲突错误

### 交接（Handoff）

- 只有当前 owner 才能发起 handoff
- 目标智能体必须存在
- `completed / failed` 终态任务不能 handoff

---

## 3. 重试规则

- 只有 `failed` 任务可以调用 `/retry`
- 超过 `max_retries` 后返回 `409`
- 重试会清理：
  - `result`
  - `consensus`
  - `proposals`
  - `current_agent_id`
- 重试后任务回到 `queued`
- 如 `requeue=true`，会重新进入 workflow

---

## 4. 事件协议

当前 `BusMessage` 结构：

```json
{
  "message_id": "msg_xxx",
  "type": "TaskUpdate",
  "sender": "workflow_engine",
  "receiver": null,
  "task_id": "task_xxx",
  "payload": {},
  "metadata": {},
  "timestamp": "2026-04-07T10:00:00Z"
}
```

### 当前主要事件类型

- `TaskRequest`
- `TaskClaim`
- `TaskUpdate`
- `TaskResult`
- `TaskHandoff`
- `TaskReject`
- `TaskRetry`
- `TaskRetryExhausted`
- `Vote`
- `ConflictNotice`
- `Decision`
- `TaskComplete`
- `TaskFailed`
- `TaskPipelineStart`
- `TaskPipelineFinish`
- `AgentExecutionStart`
- `AgentExecutionResult`
- `AgentExecutionError`

---

## 5. 路由解释协议

任务创建后，当前 workflow 会将路由解释写入：

- `task.metadata.routing`

当前字段包括：

```json
{
  "strategy": "keyword_skill_status_load",
  "priority": "high",
  "policy": {
    "policy_version": "v1",
    "skill_weight": 100,
    "status_weight": 10,
    "load_penalty": 1,
    "priority_status_bonus": {"low": 0, "medium": 2, "high": 6}
  },
  "objective_keywords": ["research", "report"],
  "selected_agent_ids": ["agent_research", "agent_writer"],
  "reason": "Selected ... using skill overlap first, then status and active task count as tie-breakers.",
  "candidates": [
    {
      "agent_id": "agent_research",
      "role": "research",
      "status": "online",
      "matched_skills": ["research"],
      "skill_score": 1,
      "status_rank": 2,
      "active_task_count": 0,
      "score_breakdown": {
        "skill_component": 100,
        "status_component": 32,
        "load_penalty_component": 0,
        "effective_status_weight": 16,
        "priority": "high"
      },
      "total_score": 120,
      "rank": 1,
      "selected": true,
      "selection_reason": "Matched skills ..."
    }
  ]
}
```

说明：

- 这是当前 MVP 的可解释路由结果
- 不是强约束协议，但字段已经实际由后端返回

### 当前新增的工作流运行态字段

`task.metadata.decomposition` 现在还会包含：

- `workflow_run`
- `dag_nodes`
- `dag_edges`
- `ready_queue`
- `dispatch_state`
- `failure_policy`（`fail_fast` 或 `continue`）

说明：

- 当前调度模式为 `mvp_linear_queue`
- 创建任务后第一个 ready 节点会立即进入 `running`
- 后续节点通过依赖完成情况从 `blocked -> ready -> running`
- workflow 内部推进当前通过 `TaskUpdate.payload.workflow_event` 表达，如 `node_dispatched`、`node_completed`、`node_failed`、`task_requeued`
- 当启用 `task.metadata.workflow_parallel_branches=true` 且模板步数>=4 时，`step_2`/`step_3` 可并行进入 `running`
- `requeue_task` 在无失败节点时会返回幂等跳过事件：`TaskUpdate.payload.workflow_event=task_requeue_skipped`
- `node_failed` 事件会包含 `failure_policy` 字段，便于前端/运维判断后续调度行为。

---

## 6. 共识协议

当前支持两种策略：

- `highest_confidence`
- `majority_vote`

`TaskConsensus` 当前结构：

```json
{
  "conflict_detected": true,
  "decision_result": {"summary": "..."},
  "decided_by": "majority_vote",
  "reason": "Conflict detected across 3 proposals...",
  "explanation": {
    "strategy": "majority_vote",
    "proposal_count": 3,
    "unique_view_count": 2,
    "selected_agent_id": "agent_writer",
    "selected_confidence": 0.9,
    "selected_summary": "Option B",
    "comparison_basis": "majority count with confidence tie-break",
    "views": []
  }
}
```

说明：

- `reason`：用户可读摘要
- `explanation`：结构化解释，适合前端展示或调试

---

## 7. 仲裁协议

真实执行时支持：

- `off`
- `judge_on_conflict`
- `judge_always`

若触发 judge 仲裁，结果中会写入：

- `result.arbitration`

当前可能字段：

```json
{
  "mode": "judge_on_conflict",
  "judge_agent_id": "agent_judge",
  "decision": "judge_override",
  "judge_summary": "...",
  "judge_metrics": {},
  "judge_triggered": true,
  "explanation": {
    "conflict_detected": true,
    "primary_summary": "...",
    "judge_summary": "...",
    "selected_summary": "...",
    "selection_basis": "judge override applied"
  }
}
```

可能的 `decision`：

- `judge_override`
- `primary_kept`
- `judge_unavailable`

---

## 8. 结构化错误协议

关键操作（claim / handoff / retry / execute 等）的错误现在使用统一 envelope，位于 FastAPI 响应的 `detail` 字段中。

示例：

```json
{
  "detail": {
    "error_code": "E_TASK_RETRY_EXHAUSTED",
    "user_message": "已达到重试上限。请先提高 max_retries 或排查失败原因后再重试。",
    "operation": "retry_task",
    "detail": "Retry limit reached",
    "task_id": "task_xxx",
    "task_status": "failed",
    "retryable": false,
    "retry_count": 1,
    "max_retries": 1
  }
}
```

### 常见字段

- `error_code`
- `user_message`
- `operation`
- `detail`
- `task_id`
- `agent_id`
- `task_status`
- `retryable`

---

## 9. WebSocket 协议

单任务事件流地址：

```text
/ws/tasks/{task_id}
```

行为：

- 建立连接后订阅指定任务的事件队列
- 每条消息直接发送为 `BusMessage` 的 JSON 结构
- 当前不支持复杂过滤，过滤主要通过 REST 事件查询完成

---

## 10. Debug / Demo Reset 协议

调试接口默认关闭，需显式设置：

- `NEXUSAI_DEBUG_API_ENABLED=true`

当前可用：

- `GET /api/debug/storage/export`
- `POST /api/debug/storage/clear`

`/clear` 支持：

- `keep_default_agents`
- `clear_events_only`
- `restore_seed`

当 `restore_seed=true` 时：

1. 清空当前任务/事件
2. 保留默认 agents（如启用）
3. 重新应用 seed 文件
4. 恢复到稳定 demo 基线


