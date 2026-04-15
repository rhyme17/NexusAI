# NexusAI 产品计划书

更新日期：2026-04-14

## 1. 项目定位

NexusAI 是一个多智能体协作中枢，面向内部测试和小规模用户场景，核心是把“提交任务 -> 协作执行 -> 返回结果”做成稳定、可观测、可运维的产品链路。

## 2. 产品目标

- 用户可稳定提交任务并获得可用结果
- 执行过程可追踪（步骤、事件、状态、结果）
- 支持真实模型执行与模拟执行双路径
- 支持用户与管理员权限隔离
- 支持本地开发与 Ubuntu 服务器部署

## 3. 目标用户与场景

### 3.1 目标用户

- 业务/研究用户：提交调研、分析、报告类任务
- 开发与运维人员：维护服务、排障、发布与回滚

### 3.2 典型任务

- 行业调研报告
- 技术方案对比
- 实验记录整理与结构化输出

## 4. 当前能力边界

### 4.1 纳入范围

- 智能体注册、发现、状态管理
- 任务创建、执行、重试、结果查询
- 执行模式（single/pipeline/parallel）
- 事件流、流程图、WebSocket 实时更新
- 基础角色权限与会话认证

### 4.2 非目标（当前阶段）

- 多租户计费与商业化结算
- 大规模分布式调度平台
- 企业级合规审计平台对接

## 5. 模块划分

### 5.1 Agent Registry

- 管理智能体身份、角色、技能和在线状态

### 5.2 Workflow & Router

- 任务拆解、路由分发、状态流转、失败重试

### 5.3 Execution Adapter

- 统一 OpenAI 兼容接口调用
- 输出结构化结果与执行指标

### 5.4 Observability

- 任务事件、尝试历史、流程可视化
- 实时事件推送与回放

### 5.5 Auth & Governance

- 用户/管理员权限边界
- 配置、发布与回滚治理

## 6. 架构视图

```text
Frontend (Next.js)
  -> API Gateway (FastAPI)
  -> Task Coordinator / Workflow / Router
  -> Agent Execution Adapter
  -> Store (SQLite default, PostgreSQL optional, JSON compatibility)
  -> Event Bus + WebSocket
```

## 7. 路线图

### M1 稳定运行

- 固化本地与 Ubuntu 部署闭环
- 保证登录、任务执行、结果返回主链路稳定
- 固化健康检查与日志排障流程

### M2 用户体验增强

- 提升中文交互一致性
- 优化任务流程图与执行解释
- 增强结果交付形态（如 `.md`、`.txt`）

### M3 运维能力增强

- 固化 SQLite 默认基线与运维流程
- 按需支持 PostgreSQL 迁移流程
- 强化权限与数据隔离策略
- 完善发布门禁与自动化回归

## 8. 成功指标

- 首次登录到拿到结果 <= 10 分钟
- 核心链路成功率 >= 95%
- 内部测试期可用性 >= 99%

## 9. 风险与控制

- 模型服务不稳定：提供超时控制和模拟降级
- 配置漂移：统一 `.env`、systemd 和部署步骤
- 文档偏移：统一以 `README.md` 和 `docs/` 为维护入口

## 10. 文档入口

- 项目总览：`README.md`
- 用户手册：`docs/user_manual.md`
- 开发与运维手册：`docs/developer_manual.md`
- API 文档：运行后访问 `/docs`

## 11. 一句话总结

NexusAI 当前阶段的目标是：让用户稳定得到任务结果，让开发运维团队可控完成部署、更新和排障。

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
- **SQLite（默认）**：任务、Agent、执行结果与状态持久化
- **PostgreSQL（可选）**：高并发或集中化部署时的扩展存储
- **JSON（兼容）**：调试/演示路径下的兼容存储

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