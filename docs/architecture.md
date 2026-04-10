# NexusAI 架构说明（MVP）

## 目标

`NexusAI` 当前实现的是一个面向产品化推进阶段的多 Agent 协作中枢 MVP：

- 接收任务
- 进行轻量任务拆解
- 根据技能/状态进行 Agent 分配
- 跟踪状态、事件、交接、重试
- 在多提案冲突时输出共识/仲裁结果
- 通过前端 Dashboard 展示运行过程

当前架构以“先跑通、可演示、可扩展”为原则，不追求生产级复杂度。

---

## 当前真实技术栈

### 后端

- `FastAPI`
- `Python 3.12+`
- `Uvicorn`
- `Pydantic`

### 前端

- `Next.js 14`
- `React`
- `TypeScript`
- `Tailwind CSS`
- `React Flow`

### 当前存储

- 默认：**内存运行态 + JSON 快照持久化**
- 可选：**SQLite 过渡存储**

> 说明：当前尚未接入 PostgreSQL / Redis，相关能力仍属于后续演进方向。

---

## 当前后端组件划分

```text
User / Frontend Dashboard
        │
        ▼
FastAPI API Gateway (`backend/app/main.py`)
        │
        ├── Agent API (`backend/app/api/agents.py`)
        ├── Task API (`backend/app/api/tasks.py`)
        ├── Debug API (`backend/app/api/debug.py`)
        └── WebSocket Events (`backend/app/api/events.py`)
                │
                ▼
        Service Layer
        ├── WorkflowService
        ├── TaskRouter
        ├── TaskStatusService
        ├── TaskExecutionCoordinator
        ├── ConsensusService
        ├── AgentExecutionService
        └── InMemoryMessageBus
                │
                ▼
        Storage Layer
        ├── InMemoryStore + JSON persistence
        └── SQLiteStore (optional)
```

---

## 核心数据流

### 1. 创建任务

1. 客户端调用 `POST /api/tasks`
2. 后端创建 `Task`
3. 记录 `TaskRequest` 事件
4. `WorkflowService` 进行轻量拆解
5. `TaskRouter` 选出候选 Agent，并生成 `routing` 解释信息
6. 任务进入 `in_progress`

### 2. 执行与模拟执行

- 模拟执行：`POST /api/tasks/{task_id}/simulate`
- 真实执行：`POST /api/tasks/{task_id}/execute`
- 预览执行计划：`POST /api/tasks/{task_id}/execute/preview`

执行过程中可能触发：

- `TaskClaim`
- `TaskHandoff`
- `TaskUpdate`
- `AgentExecutionStart`
- `AgentExecutionResult`
- `AgentExecutionError`
- `TaskComplete`
- `TaskFailed`

### 3. 冲突与共识

当多个 Agent 针对同一任务提交不同结果时：

1. 系统累计 proposal
2. `ConsensusService` 按当前策略进行判断
3. 输出 `TaskConsensus`
4. 发布 `ConflictNotice` / `Decision`
5. 若启用 judge 仲裁，还会在执行结果中写入 `arbitration` 解释

### 4. 观测与前端展示

前端通过以下方式消费后端：

- REST API：任务列表、详情、结果、尝试记录、共识、事件历史
- WebSocket：`/ws/tasks/{task_id}` 实时订阅单任务事件流

---

## 当前实现中的关键服务

### `WorkflowService`

职责：

- 任务入队
- 基于模板生成简化任务拆解
- 把分配结果、拆解结果写回任务元数据

写入的关键 metadata：

- `decomposition`
- `routing`

### `TaskRouter`

当前是 MVP 路由器，不做复杂的语义搜索。

当前考虑的因素：

- objective 关键词与 agent skills 的匹配
- agent 在线状态（`online / busy / offline`）
- 轻量负载提示（`metadata.active_task_count`）

输出：

- `selected_agent_ids`
- `candidates`
- `reason`
- `strategy`

### `TaskStatusService`

职责：

- claim / handoff
- 状态更新
- 发布状态事件
- 状态机守卫

当前已实现的守卫：

- 禁止非法状态跳转
- `failed` 任务必须先 retry 才能恢复执行
- 终态任务禁止错误的 claim / handoff

### `TaskExecutionCoordinator`

职责：

- 统一管理 simulate / preview / execute / retry
- 支持 `single` / `pipeline` / `parallel`
- 支持 fallback
- 支持 judge 仲裁模式

### `ConsensusService`

当前支持：

- `highest_confidence`
- `majority_vote`

输出除最终 decision 外，还包含结构化 `explanation`，方便前端展示“为什么选择这个结果”。

### `InMemoryMessageBus`

职责：

- 保存任务事件历史
- 提供任务级订阅能力
- 支持 WebSocket 实时事件流

---

## 存储架构说明

### 默认模式：JSON 过渡持久化

优点：

- 启动简单
- 便于团队快速验证与联调
- 人工可读、便于调试

限制：

- 不适合并发场景
- 不适合复杂查询
- 不是正式数据库方案

### 可选模式：SQLite

适合：

- 本地更稳定的持久化验证
- 在不引入完整数据库服务的情况下提升一致性

---

## 扩展点

当前代码已为后续扩展预留接口：

- 更复杂的 Agent 编排（如 LangGraph）
- 更强的 Router 策略
- 更强的 Arbitration / Judge 工作流
- PostgreSQL / Redis
- 统一鉴权、审计日志、监控

---

## 与 `prospectus.md` 的关系

当前实现已经覆盖 `prospectus.md` 中的大部分 MVP 主干：

- Agent 注册与发现
- 消息协议
- 任务拆解与基础路由
- 多 Agent 串行/并行执行 MVP
- 状态追踪、交接、失败重试
- 冲突检测与仲裁
- Dashboard 可观测展示

尚未完全进入生产化阶段的部分包括：

- 真正的数据库 / 队列系统
- 完整鉴权
- 复杂 DAG 编排
- Redis Pub/Sub
- 更强的自治 Agent 网络

