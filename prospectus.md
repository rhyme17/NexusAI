# NexusAI 项目计划书

## 1. 项目名称
**NexusAI**  
**A coordination layer for autonomous AI agents**

---

## 2. 项目背景

随着大模型和 AI Agent 能力提升，单个 Agent 已经能完成很多任务，但在真实场景中，复杂任务往往需要多个 Agent 分工协作，例如：

- 调研 + 总结 + 审校
- 计划 + 执行 + 验证
- 数据检索 + 分析 + 报告生成
- 客服分流 + 专家升级 + 风控判断

当前多 Agent 系统普遍存在以下问题：

1. Agent 之间缺乏统一通信协议
2. 任务交接不稳定，状态难以追踪
3. 多 Agent 协作容易出现冲突或重复劳动
4. 缺少自动决策与仲裁机制
5. 难以形成可扩展的 Agent 网络

因此，我们希望构建一个 **Agent 协作中枢**，让多个 AI Agent 像一个团队一样自主完成复杂任务，无需人类逐步介入。

---

## 3. 项目目标

本项目旨在构建一个支持以下能力的系统：

- **Agent 注册与发现**
- **统一消息协议**
- **任务拆解与路由**
- **多 Agent 并行协作**
- **自动交接与状态追踪**
- **冲突检测与仲裁**
- **结果校验与输出整合**
- **可视化任务流**

最终实现一个可以接收复杂目标，并自动组织多个 Agent 协同完成任务的系统。

---

## 4. 项目价值

### 4.1 对用户
用户只需输入一个目标，系统即可自动拆解任务并组织多个 Agent 完成，无需人工逐步调度。

### 4.2 对开发者
系统提供统一的 Agent 协作基础设施，支持不同角色、不同能力的 Agent 插拔式接入。

### 4.3 对评委
本项目直接体现题目中的核心要求：

- communicate
- collaborate
- make decisions with each other
- without human intervention

---

## 5. 核心功能模块

### 5.1 Agent Registry
记录每个 Agent 的能力、角色、权限和状态。

**功能包括：**
- Agent 注册/注销
- 能力标签管理
- 在线状态管理
- 按技能检索 Agent

**示例 Agent：**
- Planner Agent（任务规划）
- Research Agent（信息检索）
- Analyst Agent（数据分析）
- Writer Agent（文本生成）
- Reviewer Agent（质量审查）
- Judge Agent（冲突仲裁）

---

### 5.2 Message Bus
统一 Agent 间消息格式，支持点对点、广播、订阅等通信方式。

**消息类型包括：**
- `TaskRequest` — 任务请求
- `TaskClaim` — Agent 声称接受任务
- `TaskUpdate` — 任务进度更新
- `TaskResult` — 任务结果返回
- `TaskHandoff` — 任务交接
- `TaskReject` — 任务拒绝
- `ConflictNotice` — 冲突通知
- `Vote` — 投票
- `Decision` — 最终决策
- `TaskComplete` — 任务完成

---

### 5.3 Task Router
根据任务内容与 Agent 能力进行自动分发。

**主要能力：**
- 能力匹配（语义相似度 + 关键词匹配）
- 负载均衡（避免单个 Agent 过载）
- 优先级调度（高优先级任务优先分发）
- 子任务并行分发（并行 vs 串行编排）

---

### 5.4 Workflow Engine
将复杂任务拆解为可执行的 DAG（有向无环图）工作流，并管理任务生命周期。

**主要能力：**
- 任务拆解（LLM 驱动的任务分解）
- 依赖管理（任务间的前置依赖）
- 状态机控制（待分配 → 执行中 → 完成 → 失败）
- 重试机制（自动重试失败任务）
- 超时处理（超时自动升级）

---

### 5.5 Consensus / Arbitration Engine
在多个 Agent 输出冲突时，自动进行决策与仲裁。

**可选策略：**
- 置信度加权（按各 Agent 的输出置信度投票）
- 多数投票（多数意见优先）
- Judge Agent 仲裁（由专门 Agent 做最终判断）
- 规则优先级判断（按预设规则）

---

### 5.6 Observability Dashboard
以可视化方式展示整个 Agent 网络的运行情况。

**展示内容：**
- Agent 节点图谱（谁在网络里）
- 任务流转路径（任务怎么流转的）
- 消息记录（Agent 之间说了什么）
- 子任务状态（每个子任务的进展）
- 冲突与仲裁过程（发生了什么冲突，怎么解决的）
- 执行耗时与结果（用时多长，最终输出什么）

---

## 6. 系统架构

### 6.1 架构概览

```text
┌──────────────────────────────────────────────────────────────┐
│                         User / Client                        │
│              输入目标 / 查看任务进度 / 查看结果                 │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                  NexusAI API Gateway                         │
│          接收请求 / 鉴权 / 任务创建 / 结果查询                  │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                       Workflow Engine                        │
│   任务拆解 / DAG 编排 / 任务状态机 / 依赖管理 / 重试机制         │
└───────────────┬───────────────────────┬───────────────────────┘
                │                       │
                ▼                       ▼
┌───────────────────────┐   ┌──────────────────────────────────┐
│     Task Router       │   │          Consensus Engine        │
│ 能力匹配 / 分发任务     │   │       投票 / 仲裁 / 冲突检测      │
└───────────┬───────────┘   └──────────────────┬───────────────┘
            │                                   │
            ▼                                   ▼
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
│   任务流可视化 / Agent 图谱 / 日志 / 置信度 / 冲突记录         │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 核心流程

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

---

## 7. 协议设计

建议使用统一 JSON 消息格式，保证不同 Agent 可以互通。

### 基础消息结构

```json
{
  "message_id": "msg_uuid_123",
  "type": "TaskRequest",
  "sender": "planner_agent",
  "receiver": "research_agent",
  "task_id": "task_001",
  "timestamp": "2026-04-05T10:00:00Z",
  "payload": {
    "objective": "Research a new AI protocol",
    "constraints": ["use only public sources", "return in 3 bullet points"],
    "priority": "high",
    "deadline": "2026-04-05T12:00:00Z"
  },
  "metadata": {
    "confidence": 0.92,
    "ttl": 3,
    "max_retries": 2,
    "parent_task_id": "root_001"
  }
}
```

### 核心消息类型

| 消息类型 | 发起方 | 接收方 | 目的 |
|---------|-------|-------|------|
| `TaskRequest` | Router | Agent | 分配任务 |
| `TaskClaim` | Agent | Router | 确认接受 |
| `TaskUpdate` | Agent | Bus | 报告进度 |
| `TaskResult` | Agent | Router | 返回结果 |
| `ConflictNotice` | Router | Consensus | 上报冲突 |
| `Vote` | Agent | Consensus | 投票 |
| `Decision` | Consensus | Router | 仲裁结果 |
| `TaskComplete` | Router | User | 任务完成 |

---

## 8. 技术栈

### 8.1 后端框架
- **FastAPI**（高性能 API 框架）
- **Python 3.12+**
- **Uvicorn**（ASGI 服务器）

### 8.2 数据存储
- **PostgreSQL**（任务、Agent 注册信息、执行日志）
- **Redis**（消息队列、缓存、实时状态）

### 8.3 Agent 编排
- **LangGraph**（推荐：适合状态机和 DAG）
- **AutoGen**（可选）
- **CrewAI**（可选）

### 8.4 实时通信
- **WebSocket**（FastAPI 原生支持）
- **Redis Pub/Sub**（消息分发）

### 8.5 前端
- **Next.js 14+**
- **React**
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**
- **React Flow**（任务流可视化）

### 8.6 模型层
- **OpenAI API**
- **Anthropic Claude**
- **Gemini**
- **deepseek**
- 开源模型：**Qwen / Llama**

### 8.7 观测与日志
- **Pydantic**（数据验证）
- **Loguru**（日志）
- 可选：**OpenTelemetry**

---

## 9. 项目目录结构

```text
nexusai/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py          # 任务 API
│   │   │   ├── agents.py         # Agent 注册 API
│   │   │   ├── ws.py             # WebSocket
│   │   │   └── results.py        # 结果查询 API
│   │   ├── models/
│   │   │   ├── task.py           # 任务数据模型
│   │   │   ├── agent.py          # Agent 数据模型
│   │   │   ├── message.py        # 消息数据模型
│   │   │   └── result.py         # 结果数据模型
│   │   ├── services/
│   │   │   ├── workflow.py       # Workflow Engine
│   │   │   ├── router.py         # Task Router
│   │   │   ├── consensus.py      # Consensus Engine
│   │   │   └── message_bus.py    # Message Bus
│   │   ├── agents/
│   │   │   ├── base.py           # Agent 基类
│   │   │   ├── planner.py        # Planner Agent
│   │   │   ├── research.py       # Research Agent
│   │   │   ├── analyst.py        # Analyst Agent
│   │   │   ├── writer.py         # Writer Agent
│   │   │   ├── reviewer.py       # Reviewer Agent
│   │   │   └── judge.py          # Judge Agent
│   │   ├── core/
│   │   │   ├── config.py         # 配置
│   │   │   ├── database.py       # 数据库连接
│   │   │   └── auth.py           # 鉴权
│   │   └── utils/
│   │       └── helpers.py        # 工具函数
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   ├── TaskFlow.tsx      # 任务流可视化
│   │   │   ├── AgentGraph.tsx    # Agent 网络图
│   │   │   ├── Dashboard.tsx     # 仪表板
│   │   │   └── TaskForm.tsx      # 任务输入表单
│   │   ├── pages/
│   │   ├── styles/
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   └── README.md
├── docs/
│   ├── architecture.md
│   ├── protocol.md
│   └── api_spec.md
└── README.md
```

---

## 10. MVP 范围

### 必做功能（第 1-2 天）
1. Agent 注册接口
2. 任务创建接口
3. 基础任务拆解（简化版）
4. 3-5 个预定义 Agent
5. 消息协议与 Message Bus
6. WebSocket 实时推送

### 增强功能（第 2-3 天）
1. 任务状态机与追踪
2. 简单的 Task Router
3. 冲突检测与仲裁（投票机制）
4. 基础 Dashboard（任务列表 + 状态）

### 可选优化（第 3 天）
1. 任务可视化流图
2. Agent 网络拓扑图
3. 历史任务回放
4. 置信度评分
5. 失败重试机制

---

## 11. Demo 场景

### 场景示例

**用户输入：**
> 帮我调研一个新技术（比如 区块链在信息安全中的应用 ）并输出一份可执行方案

### Demo 流程

1. **Planner Agent** 接收任务，拆解成：
   - 研究市场现状
   - 收集技术资料
   - 评估风险与机会
   - 生成可执行方案

2. **Research Agent** 并行搜索相关资料

3. **Analyst Agent** 对资料进行分析和总结

4. **Reviewer Agent** 检查质量和完整性

5. **Writer Agent** 润色并生成最终报告

6. **Judge Agent**（如果有冲突）进行最终仲裁

7. **Dashboard** 展示：
   - 任务拆解树
   - Agent 协作过程
   - 消息流转
   - 任务状态变化
   - 最终输出结果

---

## 12. 项目亮点

- **不是单个聊天机器人**，而是一个真正的 **Agent 协作基础设施**
- **统一协议**实现 Agent 间的互操作性
- **自动编排**实现任务的自主分工
- **自治决策**让 Agent 在无人工干预下完成复杂任务
- **可视化**让协作过程透明、可解释、可追踪

---

## 15. 一句话总结

**NexusAI 是一个让多个 AI Agent 能够像团队一样协作、通信、决策和执行任务的协调中枢。**

---

## 16. 联系与支持

- **项目仓库**：[to be created]
- **技术文档**：docs/
- **API 文档**：/docs（FastAPI 自动生成）
- **问题反馈**：Issues

---