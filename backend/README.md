# NexusAI 后端 MVP

这是 NexusAI 面向产品化迭代阶段的 FastAPI 后端。它为当前的 Next.js 多工作区 Dashboard（`/`、`/tasks`、`/tasks/{taskId}`、`/agents`）提供支撑，并暴露任务、智能体、事件、重试、共识等 MVP 核心接口。

后端支持 `sqlite` / `postgres` / `json` 三种存储后端。当前默认基线为 **SQLite**，并保留 PostgreSQL 可选迁移路径。

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

## 基于文件的自动配置

- 后端启动时会自动加载 `backend/.env` 和 `backend/.env.local`（也支持通过 `NEXUSAI_ENV_FILE` 指定文件）。
- 这样可以把 Phase A 的鉴权、调试开关、启动时清理策略放到文件里，而不必每次手动导出环境变量。

示例 `backend/.env`：

```bash
NEXUSAI_API_AUTH_ENABLED=true
NEXUSAI_API_KEYS=dev-key-1,dev-key-2
NEXUSAI_DEBUG_API_ENABLED=true

# 可选：启动时重置
NEXUSAI_CLEAR_ON_STARTUP=false
NEXUSAI_CLEAR_EVENTS_ONLY_ON_STARTUP=false
NEXUSAI_CLEAR_RESTORE_SEED_ON_STARTUP=false
```

启动后常用地址：

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

如果要联调整体演示，请在 `../frontend` 目录单独启动前端：`npm run dev`。对应页面分别为：总览 `/`、任务工作区 `/tasks`、单任务工作区 `/tasks/{taskId}`、智能体视图 `/agents`。

## 当前包含的 MVP 接口

- `POST /api/agents`：注册智能体
- `GET /api/agents`：获取智能体列表
- `POST /api/tasks`：创建任务
- `GET /api/tasks/{task_id}`：获取任务状态
- `PATCH /api/tasks/{task_id}/status`：更新任务状态/结果
- `POST /api/tasks/{task_id}/claim`：为某个智能体认领任务
- `POST /api/tasks/{task_id}/handoff`：在智能体之间交接任务
- `POST /api/tasks/{task_id}/simulate`：运行轻量模拟执行（成功/失败）
- `POST /api/tasks/{task_id}/execute/preview`：预览执行计划（不修改状态）
- `POST /api/tasks/{task_id}/execute`：通过 OpenAI 兼容提供方执行真实智能体调用（可选 fallback）
- `POST /api/tasks/{task_id}/retry`：重试失败任务（可选重新入工作流队列）
- `GET /api/tasks/{task_id}/attempts`：获取尝试/重试历史快照
- `GET /api/tasks/{task_id}/result`：获取任务结果快照
- `GET /api/tasks/{task_id}/consensus`：获取共识与提案快照
- `GET /api/tasks/{task_id}/events`：获取任务事件历史（支持 `offset`、`cursor`、`limit`、`sort`、重复 `type`、`from`、`to`、`include_meta` 查询参数）
- `GET /api/tasks`：获取任务列表
- `GET /api/debug/storage/export`：导出当前存储快照（需启用 debug）
- `POST /api/debug/storage/clear`：清空当前存储快照数据（需启用 debug，可选 `restore_seed=true`）

## Phase A 基线安全能力

- 已支持对受保护路由（`/api/*`）增加可选的 API Key 门禁。
- 通过 `NEXUSAI_API_AUTH_ENABLED=true` 开启，并使用 `NEXUSAI_API_KEYS` 配置逗号分隔的 key 列表。
- 通过 `NEXUSAI_API_KEY_ROLES` 配置可选的 key-角色映射（格式：`key:role`，角色为 `admin|operator|viewer`）。
- 未映射的 key 使用 `NEXUSAI_API_AUTH_DEFAULT_ROLE`（默认 `viewer`）。
- 请求头中使用 `X-API-Key` 传递 key。
- 默认免鉴权路径：`/`、`/health`、`/docs`、`/openapi.json`、`/redoc`、`/ws/*`。

当前 Phase A 的角色门禁增量：

- 当鉴权启用时，`POST /api/debug/storage/clear` 需要 `admin` 角色。

## Phase A 审计中间件

- 每个 HTTP 请求都会输出结构化审计日志记录（`nexusai.audit`），包含：
  - `request_id`
  - `method`
  - `path`
  - `status_code`
  - `duration_ms`
  - `actor`（脱敏后的 API Key 或 `anonymous`）
- 响应头中包含 `X-Request-ID`（若请求头已带入则沿用）。

## 状态与归属守卫

- 状态更新受状态机守卫约束：终态任务不能通过直接调用 `/status` 恢复执行。
- 如果任务为 `failed`，必须先调用 `/api/tasks/{task_id}/retry` 才能回到执行状态。
- 终态任务禁止继续执行 claim/handoff，避免完成或失败后的错误归属变更。
- 非法状态跳转会返回 `409`，并带有结构化错误细节（`error_code`、`user_message`、`from_status`、`to_status`）。

## 结构化操作错误

- `claim`、`handoff`、`retry`、`execute` 的前置条件失败会统一通过 `detail` 返回 FastAPI 错误包络。
- 常见字段包括：`error_code`、`user_message`、`operation`，以及可选的 `task_id`、`agent_id`、`task_status`、`retryable`。
- 这种结构便于前端直接展示用户可读错误，而不需要为每个端点单独解析。

## WebSocket 事件

- `ws://localhost:8000/ws/tasks/{task_id}`：订阅任务事件
- 事件类型：`TaskRequest`、`TaskClaim`、`TaskUpdate`、`TaskResult`、`TaskHandoff`、`TaskReject`、`TaskRetry`、`TaskRetryExhausted`、`Vote`、`ConflictNotice`、`Decision`、`TaskComplete`、`TaskFailed`
- 扩展执行事件类型：`TaskPipelineStart`、`AgentExecutionStart`、`AgentExecutionResult`、`AgentExecutionError`、`TaskPipelineFinish`
- `TaskFailed` 的 payload 包含 `error_code`、`error_message` 和 `result`
- 示例过滤：`/api/tasks/{task_id}/events?type=TaskFailed&type=Decision&cursor=0&limit=20&sort=desc&from=2026-04-05T10:00:00Z&to=2026-04-05T12:00:00Z`
- 响应头：`X-Total-Count`（分页前的过滤总数）
- 可选包装模式：`include_meta=true` 时返回 `{ total_count, offset, limit, sort, has_more, next_cursor, items }`

## 事件历史保留策略

- 环境变量 `NEXUSAI_EVENT_HISTORY_MAX` 控制每个任务在内存和 JSON 快照中的保留事件数量。
- 默认值为 `2000`，最小有效值为 `100`。

## SQLite（默认）

- 默认存储后端：`NEXUSAI_STORAGE_BACKEND=sqlite`
- 默认 SQLite 文件：`backend/data/nexusai.db`
- 可通过 `NEXUSAI_SQLITE_PATH` 覆盖路径

## JSON 持久化（兼容/调试）

- `json` 后端可通过 `NEXUSAI_STORAGE_BACKEND=json` 启用
- 默认通过 `NEXUSAI_JSON_PERSISTENCE_ENABLED=true` 开启
- 默认数据目录：`backend/data/`
- 可通过 `NEXUSAI_DATA_DIR` 覆盖路径
- 输出文件：`tasks.json`、`agents.json`、`events.json`
- 这是一层兼容/调试用持久化方案，生产与内测推荐 SQLite 或 PostgreSQL

## PostgreSQL（可选迁移）

- 支持通过 `NEXUSAI_STORAGE_BACKEND=postgres` 切换存储后端。
- 使用 `NEXUSAI_POSTGRES_DSN` 配置 DSN。
- 当前实现保持现有 API 契约不变，并通过 JSONB 行映射任务/智能体载荷。
- 失败保护：可设置 `NEXUSAI_STORAGE_FALLBACK_ON_ERROR=true`（默认）启用自动 fallback。
- fallback 目标由 `NEXUSAI_STORAGE_FALLBACK_BACKEND` 控制（`json` 或 `sqlite`，默认 `json`）。
- 快照导出/导入工具：`python migrate_snapshot.py export --output <file>` 与 `python migrate_snapshot.py import --input <file>`。
- 快照结构校验：`python migrate_snapshot.py verify --input <file>`（推荐在 import 前执行）。
- 一键预演脚本：`python rehearse_cutover.py`（默认执行 `export -> verify -> import` 并生成 report）。
- 发布门禁脚本：`python release_gate.py --profile quick|full`（生成 `backend/data/release-gate-report.json`）。
- 发布门禁归档：`python release_gate.py --profile full --archive-history`（额外生成 `backend/data/release-gate-history/*.json`）。
- 候选切换门禁：`python release_gate.py --profile cutover_candidate`（串联 rehearsal + migration + API smoke + snapshot perf）。
- 预演预算参数：`python rehearse_cutover.py --max-total-ms <ms> --max-import-ms <ms>`（超预算会标记 failed 并输出原因）。
- 推荐切换流程见 `POSTGRES_CUTOVER_RUNBOOK.md`。

## 真实智能体执行（ModelScope / OpenAI 兼容）

- 入口：`POST /api/tasks/{task_id}/execute`
- 基于 OpenAI 兼容的 Chat Completions API（`openai` SDK 客户端）
- 默认 provider base URL：`https://api-inference.modelscope.cn/v1`
- 默认模型：`deepseek-ai/DeepSeek-V3.2`
- API Key 来源优先级：`NEXUSAI_AGENT_EXECUTION_API_KEY` > `MODELSCOPE_TOKEN`
- 支持通过请求体 `api_key` 传入用户级密钥（优先级：请求 `api_key` > `NEXUSAI_AGENT_EXECUTION_API_KEY` > `MODELSCOPE_ACCESS_TOKEN` > `MODELSCOPE_TOKEN`）
- fallback 策略环境变量：`NEXUSAI_AGENT_EXECUTION_FALLBACK`（`simulate` 或 `fail`）
- 请求可覆盖 `model`、`temperature`、`max_tokens`、`system_instruction` 与 fallback 行为
- 请求支持 `provider`（当前 MVP 值为 `openai_compatible`），为后续多 provider 扩展预留位置
- 请求支持可选 pipeline 执行（`execution_mode=pipeline`、`pipeline_agent_ids`），用于串行多智能体执行
- 请求也支持轻量 parallel 批量模式（`execution_mode=parallel`，复用 `pipeline_agent_ids`），用于 MVP 的多智能体 fan-out
- pipeline 支持 `pipeline_error_policy`（默认 `fail_fast`，也可设为 `continue` 继续后续步骤）
- 在 `parallel` 模式下，最终结果会从成功的智能体输出中选择最高置信度结果，并把成功/失败步骤细节写入 `result.parallel`
- 预览响应包含 `estimated_events`，并带有条件标记（`always`、`on_error`、`on_fallback`、`on_no_fallback`），便于前端规划时间线
- `estimated_events` 还包含可选的 `step`、`agent_id` 字段，用于逐步可视化
- 预览响应包含 `preview_warnings`（例如缺失 judge、严格失败路径、pipeline 局部成功风险），并可通过 `applies_to_step` 关联具体步骤
- 请求支持可选仲裁：`arbitration_mode`（`off`、`judge_on_conflict`、`judge_always`）和 `judge_agent_id`
- 结果包含 `execution_metrics`（`latency_ms`、provider `usage`、仲裁标志）

## 可选种子加载

- `NEXUSAI_SEED_ENABLED`：启用启动时种子导入（默认 `false`）
- `NEXUSAI_SEED_APPLY_IF_EMPTY`：仅在存储为空时应用种子（默认 `true`）
- `NEXUSAI_SEED_FILE`：覆盖种子文件路径（默认指向 `backend/data/seed.example.json`）
- 种子格式支持 `agents` 与 `tasks` 数组；每项既可以是完整模型载荷，也可以是最小创建载荷

## 演示调试存储接口

- `GET /api/debug/storage/export`：导出内存 + JSON 快照数据
- `POST /api/debug/storage/clear`：清空任务/事件（支持可选查询参数 `keep_default_agents`、`clear_events_only`、`restore_seed`）
- `restore_seed=true` 会在清空当前演示数据后立即重新应用种子文件，便于回到可复现演示基线
- 这些接口默认关闭；需通过 `NEXUSAI_DEBUG_API_ENABLED=true` 显式开启

## 共识策略

- 可在任务元数据中设置 `consensus_strategy` 为 `highest_confidence`（默认）或 `majority_vote`
- 可通过环境变量 `NEXUSAI_CONSENSUS_STRATEGY_DEFAULT` 控制全局默认策略
- 优先级：任务元数据 > 环境默认值 > 内建 fallback（`highest_confidence`）
- 创建任务示例元数据：`{ "consensus_strategy": "majority_vote" }`

## Task Router 策略（Week 2）

- 路由策略支持环境变量配置：
  - `NEXUSAI_ROUTER_SKILL_WEIGHT`
  - `NEXUSAI_ROUTER_STATUS_WEIGHT`
  - `NEXUSAI_ROUTER_LOAD_PENALTY`
  - `NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_LOW`
  - `NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_MEDIUM`
  - `NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_HIGH`
- 默认策略版本：`policy_version=v1`
- 任务级可覆盖策略：`task.metadata.routing_policy`（优先级高于环境变量）
- 路由解释新增字段：`priority`、`policy`、`candidates[].score_breakdown`

## 任务拆解模板

- 工作流拆解基于 `task.metadata.decomposition` 中的关键词匹配模板。
- 可在创建任务时按任务覆盖，例如：`{ "decomposition_template": "planning" }`。

## 工作流队列 / DAG 调度 MVP

- 创建任务时会在 `task.metadata.decomposition` 下初始化持久化工作流载荷。
- 该载荷包含 `workflow_run`、`dag_nodes`、`dag_edges`、`ready_queue`、`dispatch_state`。
- 当前调度模式为 `mvp_linear_queue`：系统会自动派发并持久化第一个 ready 节点。
- 重试会复用现有工作流图，并重新入队节点，而不是从头重建拆解结果。
- 可选失败策略：`task.metadata.workflow_failure_policy`（`fail_fast` 默认，或 `continue`）。
- 在 `continue` 策略下，失败节点后的依赖分支可继续进入 ready/running（适用于并行分支容错）。

## 重试策略

- 可通过任务元数据 `max_retries` 限制某个任务的手动重试次数。
- 全局默认值可通过环境变量 `NEXUSAI_MAX_RETRIES_DEFAULT` 控制（默认 `2`）。
- 达到上限后，`/retry` 会返回 `409`，并发出 `TaskRetryExhausted` 事件。

## 默认种子智能体

- `agent_planner`（planner）
- `agent_research`（research）
- `agent_writer`（writer）
- `agent_analyst`（analyst）
- `agent_reviewer`（reviewer）
- `agent_judge`（judge）

## 运行测试

```bash
cd backend
pytest -q
```

Phase A 聚焦检查：

```bash
pytest -q tests/test_api.py -k "api_auth_ or role_guard or audit_middleware or openapi"
pytest -q tests/test_phase_a_perf.py
```

