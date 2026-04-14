# NexusAI 黑客松汇报大纲与通信协议说明

## Part A. 5-10 分钟详细汇报大纲

> 目标：在有限时间内讲清楚“为什么需要 NexusAI、系统怎么工作、现场演示什么、现在做到哪一步”。

### 0. 时间分配建议（总时长 8 分钟，可压缩到 5 分钟）

- 00:00-00:45：问题定义与价值
- 00:45-01:20：一句话方案与系统定位
- 01:20-02:30：架构与技术实现
- 02:30-05:30：现场 Demo（核心）
- 05:30-06:30：可靠性与工程化能力
- 06:30-07:20：当前成果与可量化指标
- 07:20-08:00：下一步计划与收尾

> 若只有 5 分钟：保留“问题 -> 方案 -> Demo -> 成果”四段，各 60-90 秒。

---

### 1) 开场：为什么做这个系统（00:00-00:45）

**讲什么**

- 单个大模型能回答问题，但复杂任务需要“多角色协作”。
- 实际痛点不在回答本身，而在：任务分工、过程跟踪、失败恢复、结果可解释。

**建议话术**

- "我们不是在做一个聊天窗口，而是在做一个可运行的多智能体协作中枢。"
- "用户只管给目标，系统负责拆解、执行、回传结果，并把过程透明化。"

---

### 2) 一句话方案与定位（00:45-01:20）

**讲什么**

- NexusAI = `Task Orchestration + Agent Collaboration + Observability`。
- 用户视角：提交任务 -> 看执行 -> 拿结果。
- 运维视角：看事件、看状态、重试恢复、发布可控。

**建议话术**

- "NexusAI 把 AI 协作从‘黑盒调用’变成‘可观测、可恢复、可治理’的流程系统。"

---

### 3) 架构与实现（01:20-02:30）

**讲什么（精简版）**

- 前端：Next.js，任务台 + 单任务工作区 + Agents + 设置。
- 后端：FastAPI，任务 API、执行协调器、消息总线、WebSocket。
- 存储：JSON/SQLite/PostgreSQL（三种后端契约一致）。
- 执行：支持模拟执行与真实模型执行（OpenAI 兼容接口）。

**建议话术**

- "我们把系统拆成三层：控制层（API）、执行层（Agent Execution）、可观测层（Event Bus + WebSocket）。"
- "所以这个系统既能演示，也能逐步走向产品化部署。"

---

### 4) Demo 主线（02:30-05:30）

#### Step 1：创建任务（约 40 秒）

- 打开 `/tasks`
- 创建任务：例如“输出某技术调研报告”

**强调点**

- 任务创建后立即进入可跟踪状态，拥有独立 `task_id`。

#### Step 2：预览并执行（约 60 秒）

- 进入 `/tasks/[taskId]`
- 点击 `Preview Execution`，展示将采用的执行路径
- 点击 `Execute` 触发执行

**强调点**

- 支持 `single / pipeline / parallel` 三种模式。

#### Step 3：展示协作过程（约 60 秒）

- 展示事件流（TaskUpdate / AgentExecutionStart / AgentExecutionResult）
- 展示流程图与关键步骤状态

**强调点**

- 不是只给最终文本，而是完整过程可解释。

#### Step 4：失败恢复（约 50 秒）

- 触发失败（或展示失败任务）
- 执行 `Retry Task`

**强调点**

- 失败有结构化错误，支持重试和重试上限治理。

#### Step 5：结果交付（约 30 秒）

- 展示结果面板
- 展示导出能力（`/api/tasks/{task_id}/result/export?format=md|txt`）

**强调点**

- 用户最终拿到可用结果，而不是仅看到“运行中日志”。

---

### 5) 工程化能力与可靠性（05:30-06:30）

**讲什么**

- 接口鉴权与角色隔离（admin/user）。
- 发布门禁与回归（release gate / pytest / frontend build）。
- 服务端部署闭环（systemd + Nginx + PostgreSQL）。

**建议话术**

- "我们不仅能跑通 Demo，还建立了发布门禁、回滚与日志排障路径。"

---

### 6) 当前成果与指标（06:30-07:20）

**讲什么**

- 已覆盖主链路：创建 -> 执行 -> 结果 -> 失败恢复。
- 已支持可观测事件流与任务级 WebSocket 推送。
- 已有产品化文档与部署手册。

**可展示指标样例**

- 执行延迟（`latency_ms`）
- token 用量（`usage.total_tokens`）
- 任务成功率与重试情况

---

### 7) 下一步与收尾（07:20-08:00）

**讲什么**

- 下一步：增强结果质量评估、协议稳定性、用户体验细节与自动化回归。
- 收尾：NexusAI 目标是让多智能体协作从“演示能力”走向“可持续使用能力”。

**收尾话术**

- "我们的重点不是再造一个聊天框，而是把 AI 协作做成真正可运行的系统能力。"

---

### 8) 现场兜底策略（建议放在讲稿备注）

- 若真实模型波动：切换模拟执行路径，继续展示完整协作流程。
- 若历史数据污染：使用管理员重置接口恢复稳定基线。
- 若网络抖动：优先展示已完成任务详情与事件历史。

---

## Part B. NexusAI 消息传输与 Agents 通信协议（实现口径）

> 本节按当前代码实现总结，核心参考：`backend/app/models/message.py`、`backend/app/services/message_bus.py`、`backend/app/api/events.py`、`backend/app/api/tasks.py`、`docs/protocol.md`。

### 1) 协议目标

- 统一任务事件结构，支持 REST 查询与 WebSocket 实时推送。
- 支持任务生命周期、认领/交接、重试、执行与仲裁事件。
- 保证前后端可用同一消息模型解析与展示。

### 2) 消息模型（BusMessage）

基础结构：

```json
{
  "message_id": "msg_xxx",
  "type": "TaskUpdate",
  "sender": "workflow_engine",
  "receiver": null,
  "task_id": "task_xxx",
  "payload": {},
  "metadata": {},
  "timestamp": "2026-04-14T10:00:00Z"
}
```

字段说明：

- `message_id`：消息唯一标识
- `type`：事件类型（枚举）
- `sender/receiver`：发送方/接收方
- `task_id`：任务作用域
- `payload`：业务数据载体
- `metadata`：附加元数据
- `timestamp`：UTC 时间戳

### 3) 当前事件类型（MessageType）

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

### 4) 传输通道

#### 4.1 REST（历史查询与控制）

- 任务事件查询：`GET /api/tasks/{task_id}/events`
- 支持 `offset/limit/sort/type/from/to` 等过滤参数
- 可返回 `TaskEventsResponse`（含分页元信息）

#### 4.2 WebSocket（实时事件）

- 地址：`/ws/tasks/{task_id}`
- 建立连接后，按任务订阅消息队列
- 每条推送是一个完整 `BusMessage` JSON

### 5) Message Bus 行为（InMemoryMessageBus）

- 任务级订阅：`subscribe_task(task_id)`
- 发布：`publish()` / `publish_many()`
- 历史缓存：按 task 维护事件历史并支持上限裁剪
- 持久化：可写入 `events.json`（受配置开关控制）
- 查询：`list_task_events()` 支持过滤与排序

### 6) 任务状态与协议约束

任务状态：

- `queued`
- `in_progress`
- `completed`
- `failed`

关键约束：

- `failed -> in_progress` 不允许直接跳转，必须先 `/retry`
- `completed -> failed` 不允许
- 重试仅允许 `failed` 任务

### 7) Claim / Handoff 协议

- Claim：任务被某 agent 认领为 owner
- Handoff：仅当前 owner 可交接给目标 agent
- 终态任务（`completed/failed`）不可交接

相关接口：

- `POST /api/tasks/{task_id}/claim`
- `POST /api/tasks/{task_id}/handoff`

### 8) 执行与结果协议

执行接口：

- `POST /api/tasks/{task_id}/execute/preview`
- `POST /api/tasks/{task_id}/execute`

结果接口：

- `GET /api/tasks/{task_id}/result`
- `GET /api/tasks/{task_id}/result/export?format=md|txt`

执行结果通常包含：

- `summary`
- `mode`（`real` 或 `simulate`）
- `execution_metrics`（如 `latency_ms`、`usage`）

### 9) 错误协议（结构化）

错误统一放在响应 `detail` 中，常见字段：

- `error_code`
- `user_message`
- `operation`
- `detail`
- `task_id`
- `retryable`

示例错误码（执行相关）：

- `E_EXECUTION_CONFIG`
- `E_EXECUTION_PROVIDER`
- `E_EXECUTION_EMPTY`

### 10) 安全与可见性边界

- REST 与 WS 都遵守用户权限隔离。
- 非管理员不能访问其他用户任务。
- API Key-only 模式下，不提供跨任务可见性。

### 11) 协议演进建议（用于答辩）

- 引入协议版本号与兼容策略（新增字段向后兼容）。
- 增加事件签名/trace id，支持跨服务排障。
- 将消息总线从进程内实现演进为外部队列（可选）。

---

## 参考文件

- `docs/protocol.md`
- `backend/app/models/message.py`
- `backend/app/services/message_bus.py`
- `backend/app/api/events.py`
- `backend/app/api/tasks.py`
- `frontend/src/lib/api/types.ts`

