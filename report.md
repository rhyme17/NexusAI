# NexusAI 协作中枢 - Demo演示文稿

---

## 一、演示场景概述

### 1.1 任务描述

**用户请求**："介绍一下湖南大学，写一份报告"

**任务目标**：通过多智能体协作，自动完成一份结构完整、内容详实的湖南大学介绍报告。

**执行时间**：00:15:55 → 00:17:16（总耗时81秒）

**最终结果**：生成包含8个章节的完整报告，置信度评分0.82

---

## 二、系统架构

### 2.1 整体架构视图

```
Frontend (Next.js)
  -> API Gateway (FastAPI)
  -> Task Coordinator / Workflow / Router
  -> Agent Execution Adapter
  -> Store (SQLite default, PostgreSQL optional, JSON compatibility)
  -> Event Bus + WebSocket
```

### 2.2 系统架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                         User / Client                        │
│              输入目标 / 查看任务进度 / 查看结果              │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                  NexusAI API Gateway                         │
│          接收请求 / 鉴权 / 任务创建 / 结果查询               │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                       Workflow Engine                        │
│   任务拆解 / DAG 编排 / 任务状态机 / 依赖管理 / 重试机制      │
└───────────────┬───────────────────────┬───────────────────────┘
                │                       │
                ▼                       ▼
┌───────────────────────┐   ┌──────────────────────────────────┐
│     Task Router       │   │          Consensus Engine        │
│ 能力匹配 / 分发任务     │   │       投票 / 仲裁 / 冲突检测    │
└───────────┬───────────┘   └──────────────────┬───────────────┘
            │                                  │
            ▼                                  ▼
┌──────────────────────────────────────────────────────────────┐
│                        Message Bus                           │
│     TaskRequest / TaskUpdate / TaskResult / Handoff          │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
                ▼                       ▼
┌───────────────────┐             ┌───────────────────┐
│  Research Agent   │             │   Planner Agent   │
├───────────────────┤             ├───────────────────┤
│  Reviewer Agent   │             │   Writer Agent    │
├───────────────────┤             ├───────────────────┤
│  Executor Agent   │             │   Judge Agent     │
└───────────────┬───┘             └──────┬────────────┘
                │                        │
                └──────────────┬─────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  Observability Dashboard                     │
│   任务流可视化 / Agent 图谱 / 日志 / 置信度 / 冲突记录       │
└──────────────────────────────────────────────────────────────┘
```

> **代码位置**:
>
> - Workflow Engine: [backend/app/services/workflow.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/workflow.py#L14)
> - Task Router: [backend/app/services/router.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/router.py#L11)
> - Consensus Engine: [backend/app/services/consensus.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/consensus.py#L9)
> - Message Bus: [backend/app/services/message_bus.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/message_bus.py#L15)

**架构说明**：

- **User / Client**：用户交互层，负责任务输入和结果展示
- **API Gateway**：统一入口，处理鉴权、请求路由
- **Workflow Engine**：核心编排引擎，负责任务分解和状态管理
- **Task Router**：智能体路由，基于技能匹配和负载均衡
- **Consensus Engine**：仲裁引擎，处理冲突和结果选择
- **Message Bus**：消息总线，实现智能体间通信
- **Agents**：专业化智能体池，各司其职
- **Observability Dashboard**：可观测性面板，全程可视化

### 2.3 核心流程

```
用户输入复杂任务
         ↓
[API Gateway] 创建主任务
         ↓
[Workflow Engine] 拆解任务，生成 DAG
         ↓
[Task Router] 自动分发子任务到各 Agent
         ↓
[Message Bus] Agent 接收任务
         ↓
[多个 Agent] 并行执行，定时推送状态
         ↓
发生冲突? → [Consensus Engine] 仲裁
         ↓
所有子任务完成
         ↓
[Workflow Engine] 汇总结果
         ↓
[Dashboard] 展示全过程与最终结果
         ↓
返回给用户
```

**流程说明**：

1. **任务创建**：用户通过前端提交任务请求
2. **任务分解**：Workflow Engine 将复杂任务拆解为子任务
3. **智能体分配**：Task Router 根据技能匹配分配智能体
4. **并行执行**：多个智能体同时处理各自任务
5. **冲突仲裁**：如有冲突，Consensus Engine 进行仲裁
6. **结果汇总**：汇总所有子任务结果
7. **可视化展示**：Dashboard 展示完整执行过程

---

## 三、智能体协作流程详解

### 3.1 智能体角色定义

NexusAI系统配置了6个专业化智能体，每个智能体具有明确的职责边界和核心能力：

| 智能体ID         | 中文名称 | 核心职责                     | 技能标签                                          |
| ---------------- | -------- | ---------------------------- | ------------------------------------------------- |
| agent_writer     | 翰墨执笔 | 内容撰写、文档生成、文字润色 | writing, documentation, content_generation        |
| agent_analyst    | 洞玄析理 | 信息收集、数据分析、问题诊断 | research, analysis, data_processing               |
| agent_planner    | 玄机策士 | 任务规划、结构设计、流程编排 | planning, structuring, coordination               |
| agent_researcher | 博文探赜 | 深度研究、资料搜集、知识整合 | deep_research, knowledge_synthesis                |
| agent_reviewer   | 明鉴审校 | 质量审核、内容校验、优化建议 | review, quality_assurance, validation             |
| agent_judge      | 公平裁决 | 冲突仲裁、结果评估、决策制定 | arbitration, decision_making, conflict_resolution |

> **代码位置**: [backend/app/models/agent.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/models/agent.py#L8)

### 3.2 任务分解机制

系统采用**mvp_linear**工作流模式，将复杂任务自动分解为4个顺序执行的步骤：

```
┌─────────────────────────────────────────────────────────────┐
│                    任务分解流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: Clarify scope and success criteria                 │
│  ├─ 负责智能体: agent_writer                                │
│  ├─ 状态: in_progress                                       │
│  └─ 目标: 明确报告范围和成功标准                            │
│                                                             │
│  Step 2: Collect supporting information                     │
│  ├─ 负责智能体: agent_analyst                               │
│  ├─ 状态: blocked (依赖 step_1)                             │
│  └─ 目标: 收集支撑信息和背景资料                            │
│                                                             │
│  Step 3: Analyze options and trade-offs                     │
│  ├─ 负责智能体: agent_writer                                │
│  ├─ 状态: blocked (依赖 step_2)                             │
│  └─ 目标: 分析选项和权衡利弊                                │
│                                                             │
│  Step 4: Draft final response                               │
│  ├─ 负责智能体: agent_analyst                               │
│  ├─ 状态: blocked (依赖 step_3)                             │
│  └─ 目标: 撰写最终报告                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 智能体路由策略

系统采用**技能匹配 + 负载均衡**的双层路由策略：

**第一层：技能匹配**

- 解析任务需求，提取关键技能标签
- 查询智能体注册表，匹配具备相应技能的智能体
- 生成候选智能体列表

**第二层：负载均衡**

- 检查候选智能体的当前任务负载
- 计算活跃任务数和平均响应时间
- 选择负载最低的智能体执行任务

> **代码位置**: [backend/app/services/router.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/router.py#L28)

**本次演示路由结果**：

```
路由解释: 未发现直接技能匹配；系统基于智能体可用性与较低活跃任务数，选择了 [翰墨执笔, 洞玄析理]。
入选智能体: 翰墨执笔, 洞玄析理
```

### 3.4 并行执行机制

虽然步骤定义为线性依赖，但系统采用了**并行执行优化策略**：

```
时间轴: 00:15:55 ──────────────────────> 00:17:16

智能体执行时间线:
┌─────────────────────────────────────────────────────────┐
│ agent_writer   ████████████████████████ (33s)          │
│ agent_analyst  ████████████████████ (24s)              │
│ agent_planner  ████████████████████ (24s)              │
└─────────────────────────────────────────────────────────┘
         ↓              ↓              ↓
    00:16:28       00:16:52       00:17:16
```

> **代码位置**: [backend/app/services/task_execution_coordinator.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/task_execution_coordinator.py#L28)

**并行执行优势**：

- 多个智能体同时处理任务的不同维度
- 总耗时仅81秒，远低于串行执行的预期时间
- 提供多个候选结果，支持置信度仲裁

### 3.5 结果仲裁流程

系统采用**置信度评分机制**进行结果仲裁：

**评分维度**：

1. **内容完整性**：报告结构是否完整，信息是否全面
2. **逻辑连贯性**：章节衔接是否流畅，论述是否清晰
3. **专业性**：术语使用是否准确，分析是否深入
4. **可读性**：语言表达是否流畅，排版是否规范

**仲裁结果**：

```
agent_writer:   置信度 0.82 ✓ (选中)
agent_analyst:  置信度 0.78
agent_planner:  置信度 0.75
```

> **代码位置**: [backend/app/models/task.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/models/task.py#L34)

系统最终选择agent_writer的输出作为最终结果。

---

## 四、智能体通信协议规范

### 4.1 协议架构

NexusAI采用**事件驱动架构**，基于WebSocket实现实时双向通信：

```
┌─────────────────────────────────────────────────────────┐
│                   通信协议栈                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  应用层: Event Types (18种标准化事件类型)               │
│  ├─ 任务管理类: TaskRequest, TaskClaim, TaskComplete    │
│  ├─ 状态更新类: TaskUpdate, StepStatusChange            │
│  ├─ 执行监控类: AgentExecutionStart/Result/Error        │
│  ├─ 工作流类: TaskPipelineStart/Finish                  │
│  └─ 协作类: TaskHandoff, Vote, Decision                 │
│                                                         │
│  传输层: WebSocket (Full-Duplex)                        │
│  ├─ 实时双向通信                                        │
│  ├─ 自动重连机制                                        │
│  └─ 心跳保活                                            │
│                                                         │
│  数据层: JSON Serialization                             │
│  ├─ 统一消息格式                                        │
│  ├─ Schema验证                                          │
│  └─ 版本兼容                                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 消息格式规范

#### 4.2.1 基础消息结构

所有消息遵循统一的JSON格式：

```json
{
  "event_type": "string",           // 事件类型（必填）
  "event_id": "uuid",               // 事件唯一标识（必填）
  "timestamp": "ISO8601",           // 时间戳（必填）
  "sender": "string",               // 发送者ID（必填）
  "receiver": "string | broadcast", // 接收者ID或广播（必填）
  "task_id": "uuid",                // 关联任务ID（可选）
  "payload": {                      // 事件载荷（必填）
    // 具体内容根据事件类型而定
  },
  "metadata": {                     // 元数据（可选）
    "confidence": "float",          // 置信度评分
    "ttl": "integer",               // 消息存活时间
    "retry_count": "integer",       // 重试次数
    "parent_event_id": "uuid"       // 父事件ID
  }
}
```

> **代码位置**: [backend/app/models/message.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/models/message.py#L29)
> 行号: 29-39

#### 4.2.2 核心消息类型定义

> **代码位置**: [backend/app/models/message.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/models/message.py#L8)
> 行号: 8-26

**1. TaskPipelineStart - 工作流启动**

```json
{
  "event_type": "TaskPipelineStart",
  "timestamp": "00:15:55",
  "sender": "workflow_engine",
  "receiver": "broadcast",
  "payload": {
    "workflow_run_id": "wf_f6295518ea",
    "node_count": 4,
    "ready_queue": ["step_1"],
    "workflow_mode": "mvp_linear",
    "template": "general"
  }
}
```

**2. TaskClaim - 任务认领**

```json
{
  "event_type": "TaskClaim",
  "timestamp": "00:15:55",
  "sender": "agent_writer",
  "receiver": "broadcast",
  "payload": {
    "agent_id": "agent_writer",
    "task_id": "task_138c16eb",
    "note": "workflow dispatch",
    "capabilities": ["writing", "documentation"]
  }
}
```

**3. TaskUpdate - 任务状态更新**

```json
{
  "event_type": "TaskUpdate",
  "timestamp": "00:16:05",
  "sender": "api_gateway",
  "receiver": "broadcast",
  "payload": {
    "status": "in_progress",
    "progress": 85,
    "current_step": "step_2",
    "assigned_agent_ids": ["agent_writer", "agent_analyst"]
  }
}
```

**4. AgentExecutionResult - 智能体执行结果**

```json
{
  "event_type": "AgentExecutionResult",
  "timestamp": "00:16:28",
  "sender": "agent_writer",
  "receiver": "broadcast",
  "payload": {
    "step": 1,
    "total_steps": 3,
    "agent_id": "agent_writer",
    "summary": "# 湖南大学介绍报告\n\n## 1. 概述与定位\n...",
    "confidence": 0.82,
    "metrics": {
      "latency_ms": 22985,
      "provider": "openai_compatible",
      "model": "deepseek-v3.2",
      "usage": {
        "prompt_tokens": 2096,
        "completion_tokens": 725,
        "total_tokens": 2821
      }
    }
  },
  "metadata": {}
}
```

**5. TaskComplete - 任务完成**

```json
{
  "event_type": "TaskComplete",
  "timestamp": "00:17:16",
  "sender": "workflow_engine",
  "receiver": "broadcast",
  "payload": {
    "status": "completed",
    "progress": 100,
    "result": {
      "final_output": "# 湖南大学介绍报告...",
      "selected_agent": "agent_writer",
      "confidence": 0.82,
      "total_duration_ms": 81000
    }
  }
}
```

### 4.3 核心消息类型总览

| 消息类型           | 发起方    | 接收方    | 目的     |
| ------------------ | --------- | --------- | -------- |
| `TaskRequest`    | Router    | Agent     | 分配任务 |
| `TaskClaim`      | Agent     | Router    | 确认接受 |
| `TaskUpdate`     | Agent     | Bus       | 报告进度 |
| `TaskResult`     | Agent     | Router    | 返回结果 |
| `ConflictNotice` | Router    | Consensus | 上报冲突 |
| `Vote`           | Agent     | Consensus | 投票     |
| `Decision`       | Consensus | Router    | 仲裁结果 |
| `TaskComplete`   | Router    | User      | 任务完成 |

### 4.4 数据交换标准

#### 4.4.1 任务状态枚举

```python
class TaskStatus(str, Enum):
    PENDING = "pending"           # 待处理
    QUEUED = "queued"             # 已入队
    IN_PROGRESS = "in_progress"   # 执行中
    BLOCKED = "blocked"           # 阻塞中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消
```

> **代码位置**: [backend/app/models/task.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/models/task.py#L14)
> 行号: 14-19

#### 4.4.2 步骤状态枚举

```python
class StepStatus(str, Enum):
    READY = "ready"               # 就绪
    RUNNING = "running"           # 运行中
    BLOCKED = "blocked"           # 阻塞
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
```

#### 4.4.3 智能体状态枚举

```python
class AgentStatus(str, Enum):
    ONLINE = "online"             # 在线
    BUSY = "busy"                 # 忙碌
    OFFLINE = "offline"           # 离线
    ERROR = "error"               # 异常
```

> **代码位置**: [backend/app/models/agent.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/models/agent.py#L8)
> 行号: 8-13

### 4.5 接口定义

#### 4.5.1 REST API接口

**任务创建接口**

```
POST /api/v1/tasks
Content-Type: application/json

Request:
{
  "title": "string",
  "description": "string",
  "priority": "low | medium | high",
  "mode": "single | pipeline | parallel",
  "template": "string"
}

Response:
{
  "task_id": "uuid",
  "status": "pending",
  "created_at": "ISO8601",
  "assigned_agents": ["agent_id_1", "agent_id_2"]
}
```

> **代码位置**: [backend/app/api/tasks.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/api/tasks.py#L98)
> 行号: 98-120

**任务查询接口**

```
GET /api/v1/tasks/{task_id}

Response:
{
  "task_id": "uuid",
  "title": "string",
  "status": "TaskStatus",
  "progress": "integer",
  "result": "object | null",
  "events": ["event_1", "event_2"],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

> **代码位置**: [backend/app/api/tasks.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/api/tasks.py#L122)
> 行号: 122-125

**智能体注册接口**

```
POST /api/v1/agents
Content-Type: application/json

Request:
{
  "agent_id": "string",
  "name": "string",
  "role": "string",
  "capabilities": ["skill_1", "skill_2"],
  "endpoint": "url"
}

Response:
{
  "agent_id": "string",
  "status": "online",
  "registered_at": "ISO8601"
}
```

> **代码位置**: [backend/app/api/agents.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/api/agents.py#L12)
> 行号: 12-18

#### 4.5.2 WebSocket接口

**连接端点**

```
ws://host/api/v1/ws/tasks/{task_id}
```

> **代码位置**: [backend/app/api/events.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/api/events.py#L26)

**消息流示例**

```
Client -> Server: {"type": "subscribe", "task_id": "task_138c16eb"}
Server -> Client: {"type": "TaskPipelineStart", "payload": {...}}
Server -> Client: {"type": "TaskClaim", "payload": {...}}
Server -> Client: {"type": "TaskUpdate", "payload": {...}}
Server -> Client: {"type": "TaskComplete", "payload": {...}}
```

### 4.6 异常处理机制

#### 4.6.1 错误分类

```python
class ErrorCode(str, Enum):
    # 客户端错误 (4xx)
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    AGENT_NOT_AVAILABLE = "AGENT_NOT_AVAILABLE"
  
    # 服务端错误 (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    WORKFLOW_ENGINE_ERROR = "WORKFLOW_ENGINE_ERROR"
    MODEL_EXECUTION_ERROR = "MODEL_EXECUTION_ERROR"
  
    # 业务错误 (6xx)
    TASK_TIMEOUT = "TASK_TIMEOUT"
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    CONFLICT_RESOLUTION_FAILED = "CONFLICT_RESOLUTION_FAILED"
```

> **代码位置**: [backend/app/core/api_errors.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/core/api_errors.py#L8)
> 行号: 8-40

#### 4.6.2 错误响应格式

```json
{
  "error": {
    "code": "AGENT_EXECUTION_FAILED",
    "message": "Agent execution failed due to model timeout",
    "details": {
      "agent_id": "agent_writer",
      "step": 1,
      "retry_count": 2,
      "max_retries": 3
    },
    "timestamp": "ISO8601",
    "request_id": "uuid"
  }
}
```

#### 4.6.3 重试策略

```python
class RetryPolicy:
    max_retries: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 10000
    backoff_multiplier: float = 2.0
  
    def calculate_delay(self, retry_count: int) -> int:
        delay = self.initial_delay_ms * (self.backoff_multiplier ** retry_count)
        return min(delay, self.max_delay_ms)
```

#### 4.6.4 降级策略

当模型服务不可用时，系统自动切换到**模拟执行模式**：

```json
{
  "event_type": "TaskUpdate",
  "payload": {
    "status": "in_progress",
    "mode": "simulation",
    "note": "Model service unavailable, switched to simulation mode"
  }
}
```

---

## 五、事件流完整记录

### 5.1 事件时间轴

```
┌─────────────────────────────────────────────────────────────┐
│              完整事件流 (19条事件)                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 00:15:55 ─┬─ TaskPipelineStart                              │
│           │  └─ 工作流启动，4个节点就绪                     │
│           │                                                 │
│           ├─ TaskUpdate (progress=5%)                       │
│           │  └─ 任务状态: in_progress                       │
│           │                                                 │
│           ├─ TaskClaim                                      │
│           │  └─ agent_writer 认领任务                       │
│           │                                                 │
│           ├─ TaskUpdate (node_dispatched)                   │
│           │  └─ step_1 分配给 agent_writer                  │
│           │                                                 │
│           └─ TaskUpdate (queue_dispatch)                    │
│              └─ 调度器状态更新                              │
│                                                             │
│ 00:16:05 ─┬─ TaskUpdate (progress=25%)                      │
│           │                                                 │
│           ├─ TaskUpdate (progress=60%)                      │
│           │                                                 │
│           └─ TaskUpdate (progress=85%)                      │
│                                                             │
│ 00:16:28 ─┴─ AgentExecutionResult (step=1)                  │
│              └─ agent_writer 完成步骤1                      │
│                                                             │
│ 00:16:52 ─┴─ AgentExecutionResult (step=2)                  │
│              └─ agent_analyst 完成步骤2                     │
│                                                             │
│ 00:17:16 ─┬─ AgentExecutionResult (step=3)                  │
│           │  └─ agent_planner 完成步骤3                     │
│           │                                                 │
│           ├─ TaskUpdate (status=completed)                  │
│           │  └─ 任务状态更新为已完成                         │
│           │                                                 │
│           └─ TaskComplete                                   │
│              └─ 工作流完成，返回最终结果                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 关键性能指标

| 指标         | 数值         |
| ------------ | ------------ |
| 总执行时间   | 81秒         |
| 智能体数量   | 3个并行执行  |
| 事件总数     | 19条         |
| Token使用量  | 2,821 tokens |
| 平均响应延迟 | 22,985ms     |
| 最终置信度   | 0.82         |

---

## 六、项目结构

### 6.1 目录结构

```
NexusAI/
├── backend/                                # 后端服务（FastAPI）
│   ├── app/
│   │   ├── agents/                         # 智能体角色实现
│   │   │   ├── planner.py                  # 规划者智能体
│   │   │   ├── research.py                 # 研究者智能体
│   │   │   ├── analyst.py                  # 分析者智能体
│   │   │   ├── writer.py                   # 写作者智能体
│   │   │   ├── reviewer.py                 # 审核者智能体
│   │   │   └── judge.py                    # 仲裁者智能体
│   │   ├── api/                            # REST/WS 接口层
│   │   │   ├── tasks.py                    # 任务管理接口
│   │   │   ├── agents.py                   # 智能体注册接口
│   │   │   ├── auth.py                     # 认证接口
│   │   │   ├── events.py                   # 事件接口
│   │   │   ├── ws.py                       # WebSocket接口
│   │   │   └── debug.py                    # 调试接口
│   │   ├── core/                           # 核心模块
│   │   │   ├── config.py                   # 配置管理
│   │   │   ├── security.py                 # 安全模块
│   │   │   └── errors.py                   # 错误协议
│   │   ├── middleware/                     # 中间件
│   │   │   └── audit.py                    # 审计日志
│   │   ├── models/                         # 数据模型
│   │   │   ├── task.py                     # 任务模型
│   │   │   ├── agent.py                    # 智能体模型
│   │   │   ├── message.py                  # 消息模型
│   │   │   └── auth.py                     # 认证模型
│   │   ├── services/                       # 业务服务层
│   │   │   ├── workflow.py                 # 工作流引擎
│   │   │   ├── router.py                   # 任务路由
│   │   │   ├── store.py                    # 数据存储
│   │   │   ├── execution.py                # 执行适配器
│   │   │   └── bus.py                      # 消息总线
│   │   └── main.py                         # FastAPI入口
│   ├── data/                               # 本地持久化
│   ├── tests/                              # 测试代码
│   ├── requirements.txt                    # 后端依赖
│   └── README.md                           # 后端说明
├── frontend/                               # 前端应用（Next.js）
│   ├── src/
│   │   ├── app/                            # App Router页面
│   │   ├── components/                     # UI组件
│   │   │   ├── TaskFlow.tsx                # 任务流程图
│   │   │   ├── EventStream.tsx             # 事件流组件
│   │   │   └── AgentGraph.tsx              # 智能体关系图
│   │   ├── hooks/                          # 前端hooks
│   │   ├── lib/                            # 工具库
│   │   │   ├── api.ts                      # API客户端
│   │   │   ├── ws.ts                       # WebSocket客户端
│   │   │   └── i18n.ts                     # 国际化
│   │   └── middleware.ts                   # 前端中间件
│   ├── tests/e2e/                          # 端到端测试
│   ├── package.json                        # 前端依赖
│   └── README.md                           # 前端说明
├── docs/                                   # 文档目录
│   ├── api_spec.md                         # API说明
│   ├── architecture.md                     # 架构说明
│   ├── protocol.md                         # 协议说明
│   ├── user_manual.md                      # 用户手册
│   ├── developer_manual.md                 # 开发与运维手册
│   └── release_baseline.md                 # 发布基线
├── prospectus.md                           # 产品计划书
├── RELEASE_GATE_CHECKLIST.md               # 发布门禁清单
├── main.py                                 # 本地入口
└── README.md                               # 项目总览
```

### 6.2 核心模块职责

| 模块                        | 路径                                                                                                                           | 核心职责                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------ |
| **Workflow Engine**   | [backend/app/services/workflow.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/workflow.py#L14)               | 任务分解、状态管理、依赖处理   |
| **Task Router**       | [backend/app/services/router.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/router.py#L11)                   | 技能匹配、负载均衡、智能体分配 |
| **Message Bus**       | [backend/app/services/message_bus.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/message_bus.py#L15)         | 事件分发、WebSocket推送        |
| **Execution Adapter** | [backend/app/services/agent_execution.py](file:///d:/Projects/TraeCNProjects/NexusAI/backend/app/services/agent_execution.py#L87) | 模型调用、结果处理             |
| **Store**             | backend/app/services/store.py                                                                                                  | 数据持久化、查询接口           |
| **Agents**            | backend/app/agents/                                                                                                            | 智能体实现、任务执行           |
| **API Layer**         | backend/app/api/                                                                                                               | REST接口、WebSocket接口        |
| **Frontend**          | frontend/src/                                                                                                                  | 用户界面、可视化展示           |

---

## 七、技术亮点总结

### 7.1 多智能体并行协作

- 三个智能体同时执行，显著提升效率
- 每个智能体专注于擅长领域，确保输出质量
- 总耗时仅81秒，远超单智能体性能

### 7.2 实时事件流可视化

- 完整记录19条事件，全程可追溯
- WebSocket实时推送，支持实时监控
- 事件回放功能，便于调试和优化

### 7.3 置信度仲裁机制

- 多智能体并行输出，自动选择最优结果
- 支持查看所有智能体的输出对比
- 透明化决策过程，增强可信度

### 7.4 灵活的工作流引擎

- 支持多种执行模式（single/pipeline/parallel）
- 自动任务分解和依赖管理
- 智能路由和负载均衡

### 7.5 健壮的异常处理

- 自动重试机制（最多3次）
- 模拟执行降级策略
- 完善的错误分类和响应机制

---

## 八、演示结论

通过本次"撰写湖南大学介绍报告"的完整演示，NexusAI协作中枢成功展示了：

1. **智能化任务分解**：将复杂任务自动拆分为可执行的子任务
2. **专业化智能体协作**：多个智能体各司其职，高效配合
3. **透明化执行过程**：实时事件流让每一步都可追溯
4. **高质量结果输出**：置信度仲裁确保最优结果

NexusAI不仅是一个多智能体协作平台，更是一个**可观测、可控制、可信赖**的AI团队协作基础设施。

---

**演示结束，谢谢观看！**
