# NexusAI API 规格说明（MVP）

本文档仅描述当前代码中已经存在并可调用的接口。

基础地址（本地默认）：

```text
http://localhost:8000
```

Phase A（可选）鉴权头：

```text
X-API-Key: <your-key>
```

当后端启用 `NEXUSAI_API_AUTH_ENABLED=true` 时，`/api/*` 路由需要该请求头。

可选角色映射：

- `NEXUSAI_API_KEY_ROLES=key1:admin,key2:viewer`
- 未映射 key 使用 `NEXUSAI_API_AUTH_DEFAULT_ROLE`（默认 `viewer`）

---

## 1. 系统接口

### `GET /`

返回后端运行提示。

### `GET /health`

返回健康状态：

```json
{"status": "ok", "read_only": false, "storage_backend": "json"}
```

---

## 2. 智能体接口

### `POST /api/agents`

注册智能体。

请求体示例：

```json
{
  "name": "planner-1",
  "role": "planner",
  "skills": ["plan", "research"]
}
```

### `GET /api/agents`

返回智能体列表。

---

## 3. 任务接口

### `POST /api/tasks`

创建任务，并自动进入工作流。

请求体示例：

```json
{
  "objective": "research and summarize an AI trend",
  "priority": "high",
  "metadata": {
    "max_retries": 1,
    "consensus_strategy": "majority_vote"
  }
}
```

响应中的 `metadata` 当前通常包含：

- `decomposition`（拆解信息）
- `routing`（路由说明）

### `GET /api/tasks`

返回任务列表。

### `GET /api/tasks/{task_id}`

返回单任务详情。

### `PATCH /api/tasks/{task_id}/status`

手动更新任务状态，用于模拟推进或测试。

请求体示例：

```json
{
  "status": "completed",
  "progress": 100,
  "agent_id": "agent_writer",
  "confidence": 0.92,
  "result": {
    "summary": "final answer"
  }
}
```

### `POST /api/tasks/{task_id}/claim`

认领任务归属。

### `POST /api/tasks/{task_id}/handoff`

将任务交接给另一智能体。

### `POST /api/tasks/{task_id}/simulate`

执行模拟路径。

支持参数示例：

```json
{
  "mode": "failure",
  "simulate_handoff": true,
  "error_message": "simulated worker timeout"
}
```

### `POST /api/tasks/{task_id}/execute/preview`

无副作用预览执行步骤、预计事件与告警。

### `POST /api/tasks/{task_id}/execute`

真实执行入口。

当前支持：

- `execution_mode`: `single | pipeline | parallel`
- `provider`: `openai_compatible`
- `allow_fallback`
- `fallback_mode`: `simulate | fail`
- `arbitration_mode`: `off | judge_on_conflict | judge_always`
- `pipeline_error_policy`: `fail_fast | continue`

请求体示例：

```json
{
  "execution_mode": "pipeline",
  "api_key": "your-user-supplied-key",
  "pipeline_agent_ids": ["agent_planner", "agent_research", "agent_writer"],
  "allow_fallback": true,
  "fallback_mode": "simulate",
  "arbitration_mode": "judge_on_conflict",
  "judge_agent_id": "agent_judge"
}
```

说明：

- `api_key` 为可选字段；若传入则优先于服务端环境变量。
- 若不传，后端继续使用 `NEXUSAI_AGENT_EXECUTION_API_KEY` 或 `MODELSCOPE_TOKEN`。

### `POST /api/tasks/{task_id}/retry`

重试失败任务。

请求体示例：

```json
{
  "reason": "retry after provider failure",
  "requeue": true
}
```

### `GET /api/tasks/{task_id}/attempts`

返回尝试历史与重试计数。

### `GET /api/tasks/{task_id}/result`

返回结果快照。

### `GET /api/tasks/{task_id}/result/export?format=md|txt`

下载任务结果文件：

- `format=md`：返回 Markdown 文件
- `format=txt`：返回纯文本文件

响应头含 `Content-Disposition: attachment; filename="..."`，可直接用于前端下载。

### `GET /api/tasks/{task_id}/consensus`

返回共识结果与 proposal 列表。

---

## 4. 任务事件

### `GET /api/tasks/{task_id}/events`

返回任务事件历史。

支持的查询参数：

- `offset`
- `limit`
- `sort=asc|desc`
- `include_meta=true|false`
- `cursor`
- `type`（可重复）
- `from`
- `to`

示例：

```text
/api/tasks/{task_id}/events?type=TaskFailed&type=Decision&limit=20&sort=desc
```

响应头：

- `X-Total-Count`

当 `include_meta=true` 时，返回：

```json
{
  "total_count": 12,
  "offset": 0,
  "limit": 20,
  "sort": "desc",
  "has_more": false,
  "next_cursor": null,
  "items": []
}
```

---

## 5. WebSocket 实时流

### `WS /ws/tasks/{task_id}`

订阅指定任务的实时事件流。

每条消息都是 `BusMessage` JSON。

---

## 6. 调试存储接口

> 默认关闭，必须设置 `NEXUSAI_DEBUG_API_ENABLED=true`

### `GET /api/debug/storage/export`

导出当前 store + event bus 快照。

### `POST /api/debug/storage/clear`

清空任务/事件。

当 API 鉴权启用时，该接口额外要求 `admin` 角色。

当后端启用 `NEXUSAI_READ_ONLY_MODE=true` 时，所有 `/api/*` 写入接口还会被统一拒绝，并返回：

- `503`
- `error_code=E_SYSTEM_READ_ONLY`

支持 query：

- `keep_default_agents=true|false`
- `clear_events_only=true|false`
- `restore_seed=true|false`

说明：

- `restore_seed=true`：清空后重新加载 seed 数据
- `clear_events_only=true` 时不可同时使用 `restore_seed=true`

---

## 7. 结构化错误格式

关键操作的错误响应当前为：

```json
{
  "detail": {
    "error_code": "E_TASK_ALREADY_CLAIMED",
    "user_message": "该任务已被其他 Agent 占用。",
    "operation": "claim_task",
    "detail": "Task already claimed by another agent",
    "task_id": "task_xxx",
    "agent_id": "agent_writer",
    "task_status": "in_progress",
    "current_agent_id": "agent_planner"
  }
}
```

常见 `error_code` 示例：

- `E_TASK_NOT_FOUND`
- `E_AGENT_NOT_FOUND`
- `E_TASK_ALREADY_CLAIMED`
- `E_TASK_TERMINAL_CLAIM`
- `E_TASK_TERMINAL_HANDOFF`
- `E_TASK_HANDOFF_OWNER_MISMATCH`
- `E_TASK_RETRY_INVALID_STATE`
- `E_TASK_RETRY_EXHAUSTED`
- `E_TASK_INVALID_STATUS_TRANSITION`

---

## 8. 当前前端依赖的主要接口

当前前端 Dashboard 主要依赖以下端点：

- `GET /health`
- `GET /api/agents`
- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/claim`
- `POST /api/tasks/{task_id}/handoff`
- `POST /api/tasks/{task_id}/simulate`
- `POST /api/tasks/{task_id}/execute/preview`
- `POST /api/tasks/{task_id}/execute`
- `POST /api/tasks/{task_id}/retry`
- `GET /api/tasks/{task_id}/attempts`
- `GET /api/tasks/{task_id}/result`
- `GET /api/tasks/{task_id}/consensus`
- `GET /api/tasks/{task_id}/events`
- `WS /ws/tasks/{task_id}`

