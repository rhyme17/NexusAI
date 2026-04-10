# NexusAI

<div align="center">

[![许可证: MIT](https://img.shields.io/badge/许可证-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

**AI 智能体协作网络的编排中枢**

让多个 AI Agent 像团队一样通信、协作、决策与执行。

</div>

---

## 项目简介

NexusAI 是一个进入产品化推进阶段的多智能体协作中枢。它的目标不是做一个单独的聊天机器人，而是提供一层轻量的协调基础设施，让多个不同角色的
Agent 围绕同一个任务进行拆解、分发、执行、交接、重试、仲裁和结果汇总。

当前版本采用 **FastAPI + Python 3.12** 构建后端，以 **Next.js 14 + React + TypeScript** 构建前端
Dashboard。前端目前已从“单页大面板”重构为多工作区结构（`/` 总览、`/tasks` 任务台、`/tasks/[taskId]` 单任务工作区、`/agents` 智能体视图），优先保证“项目能跑、能力可演示、过程可观测、后续易扩展”。数据层当前采用**内存运行态 + JSON 文件过渡持久化**，适合本地演示和快速迭代。

本项目的设计方向与 `prospectus.md` 中的目标保持一致，重点体现以下能力：

- Agent 注册与发现
- 统一任务与消息流转
- 任务拆解与轻量路由
- 状态追踪与失败重试
- 冲突检测与共识结果展示
- 通过 Dashboard 可视化整个协作过程

---

## 当前已实现的 MVP 能力

目前 NexusAI 已经具备一条完整的演示闭环：用户可以提交任务，系统会生成任务实体并进入工作流；前端可以查看任务列表、任务详情、事件流、任务分解结构以及参与的
Agent；在任务详情中可以模拟成功、模拟失败、执行重试、进行 claim 和 handoff，并查看共识结果、失败记录和历史尝试。

后端已经实现了核心 API，包括 Agent 注册与查询、任务创建与查询、任务状态更新、任务结果查询、任务事件历史查询、任务
claim/handoff、失败重试、共识信息查询以及 WebSocket 事件推送。前端 Dashboard 则在分层工作区中提供系统总览、任务筛选、执行控制、事件过滤、Agent
高亮、任务流程图和共识对比视图等能力。

前端 `/agents` 页面现在也提供了 Agent 注册表单（name/role/skills），可直接通过 UI 创建 Agent 并刷新视图；用户可在侧边栏“用户 AI Key”窗口统一设置自己的 `MODELSCOPE_ACCESS_TOKEN`（浏览器本地保存），任务执行面板不再需要重复输入。后端仍支持环境变量回退（并兼容 `MODELSCOPE_ACCESS_TOKEN` / `MODELSCOPE_TOKEN`）。

为了保证这套 MVP 在演示前是可验证的，项目已经补齐了前端单元测试、Hook 测试、组件测试以及 Playwright
端到端测试。当前经过实际验证的路径包括：创建任务后直接模拟成功、任务失败后重试再成功、达到重试上限后显示错误并保持失败状态。

---

## 项目结构

项目按前后端分层组织：

- `backend/`：FastAPI 服务、Pydantic 模型、Agent 定义、任务路由、消息总线、共识与工作流服务。
- `frontend/`：Next.js Dashboard，包含任务视图、事件视图、Agent 面板、流程图、前端 API 客户端和自动化测试。
- `prospectus.md`：项目计划书与目标定义。
- `README.md`：项目总览与快速开始。

如果你需要看模块细节，建议优先阅读：

- `backend/README.md`
- `frontend/README.md`

---

## 本地启动方式（已验证）

### 1. 启动后端

在第一个终端中执行：

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

启动后可访问：

- API 根地址：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`
- Swagger 文档：`http://localhost:8000/docs`

### 2. 启动前端

在第二个终端中执行：

```bash
cd frontend
npm install
npm run dev
```

启动后可访问：

- Dashboard：`http://localhost:3000`

---

## 当前推荐的演示路径

最适合演示的方式是先启动后端和前端，然后在浏览器中按下面顺序操作：

先打开首页 `/`，快速说明系统总览和最近任务；再进入 `/tasks` 创建一个任务（例如“调研某项技术并输出执行方案”）；创建后页面会自动进入 `/tasks/[taskId]`，在单任务工作区展示任务详情、执行控制、事件流和流程图；接着触发一次
`Simulate Failure`，展示失败状态、尝试记录和错误提示；然后点击 `Retry Task` 重新进入流程，再执行一次 `Simulate Success`，最终展示任务转为 `completed`；最后可切换到 `/agents` 展示角色网络、任务相关 Agent 高亮与协作关系。

这个路径能够覆盖当前阶段最关键的几个点：任务流转、失败恢复、协作过程透明、以及最终结果的可解释性。

### 5-8 分钟固定演示脚本（可复现）

#### 0) 演示前重置到稳定基线（可选但强烈建议）

先开启 debug API：

```powershell
$env:NEXUSAI_DEBUG_API_ENABLED = "true"
$env:NEXUSAI_SEED_ENABLED = "true"
```

服务启动后执行：

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/debug/storage/clear?restore_seed=true"
```

预期：返回 `seed_restored=true`。

#### 1) 首页（约 60 秒）

- 打开 `/`
- 讲解健康状态、任务/Agent 数量、最近任务

#### 2) 任务台（约 60-90 秒）

- 打开 `/tasks`
- 创建任务（建议目标：调研某技术并给出执行方案）
- 自动跳转到 `/tasks/[taskId]`

#### 3) 单任务执行（约 2-3 分钟）

- 在执行页先点击 `Preview Execution`
- 再点击 `Execute`
- 展示执行预览（steps/events/warnings）与最终状态变化

#### 4) 失败恢复（约 90 秒）

- 点击 `Simulate Failure`
- 展示错误提示、attempts 记录与事件流
- 点击 `Retry Task` 后再 `Simulate Success`

#### 5) 协作可解释性（约 60-90 秒）

- 在任务详情展示：
  - Routing explanation（为何分配给这些 Agent）
  - Consensus explanation（为何选择该结果）
  - Arbitration explanation（若触发 judge）

#### 6) Agent 视图收尾（约 45 秒）

- 打开 `/agents`
- 展示角色、状态、技能，以及任务相关 Agent 高亮

#### 兜底策略

- 若真实模型执行不稳定：优先使用 `simulate` 路径完成演示闭环。
- 若数据污染：再次调用 `clear?restore_seed=true` 回到初始状态。

---

## 已实现的核心后端能力

后端当前是一个可运行的 FastAPI MVP，重点提供一套轻量但清晰的协作骨架。它支持默认 Agent
初始化、任务创建、任务状态管理、消息事件记录、任务事件查询、失败重试策略和共识结果查询。

其中已经可用的能力包括：

- `POST /api/agents` 与 `GET /api/agents`
- `POST /api/tasks` 与 `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}/status`
- `POST /api/tasks/{task_id}/claim`
- `POST /api/tasks/{task_id}/handoff`
- `POST /api/tasks/{task_id}/simulate`
- `POST /api/tasks/{task_id}/execute`
- `POST /api/tasks/{task_id}/retry`
- `GET /api/tasks/{task_id}/attempts`
- `GET /api/tasks/{task_id}/result`
- `GET /api/tasks/{task_id}/consensus`
- `GET /api/tasks/{task_id}/events`
- `WS /ws/tasks/{task_id}`

当前默认内置的 Agent 包括：`agent_planner`、`agent_research`、`agent_writer`、`agent_analyst`、`agent_reviewer`、`agent_judge`。

真实执行入口 `POST /api/tasks/{task_id}/execute` 支持可选仲裁参数（如 `arbitration_mode=judge_on_conflict`、`judge_agent_id`）、`provider=openai_compatible` 扩展位，以及多 Agent 串行 / 并行 MVP 执行（`execution_mode=pipeline|parallel`、`pipeline_agent_ids`），并在结果中返回 `execution_metrics`（例如延迟和 token 用量）。
另外提供 `POST /api/tasks/{task_id}/execute/preview` 用于无副作用预览执行序列；pipeline 可配置 `pipeline_error_policy`（`fail_fast` 或 `continue`）。
`/execute/preview` 还会返回 `estimated_events`（含条件标记），便于前端在真正执行前渲染预估事件时间线。
现在 `estimated_events` 还包含可选的 `step`、`agent_id`，并新增 `preview_warnings`（例如 judge 缺失、严格失败路径、pipeline 局部成功风险）；其中部分 warning 还支持 `applies_to_step`，可直接标记到具体步骤。
对于真实执行失败路径，后端现在还会返回结构化错误信息字段，例如 `error_category`、`retryable`、`user_message`，并在 fallback 结果与事件流中保持一致，便于前端展示用户可读提示。

---

## 已实现的核心前端能力

前端 Dashboard 目前已经是一个完整可操作的 MVP 界面，而不是单纯的静态展示页。它将信息按用户任务拆为多个工作区，避免把所有能力集中在同一屏。

具体来说，前端目前已经具备：

- 总览页（`/`）：显示后端健康、任务数量、Agent 数量、当前焦点任务与最近任务
- 任务台（`/tasks`）：支持创建任务、按状态筛选、仅看冲突任务、显示 `shown / total`
- 单任务工作区（`/tasks/[taskId]`）：支持模拟成功、模拟失败、重试、claim、handoff，并聚合执行控制、事件流和流程图
- 结果与元数据：展示任务结果、任务元数据、handoff 历史、attempt 历史
- 共识可视化：展示 proposal 列表和 decision 对比表
- 事件流：支持历史事件查看、WebSocket 实时流、类型/时间过滤、payload 展开
- 流程图：通过 React Flow 展示任务分解 DAG
- 智能体页（`/agents`）：展示角色、状态、技能，并高亮当前任务相关 Agent
- 中英切换：默认中文显示，并支持一键切换 English
- 执行控制：可在任务详情中配置 single/pipeline/parallel，预览执行步骤/事件/告警并触发执行

---

## 测试与质量校验

当前项目已经具备面向演示的测试闭环。前端既有 Vitest 单元测试，也有 Playwright 端到端测试；后端则提供 pytest 测试集。

### 前端常用命令

```bash
cd frontend
npm run typecheck
npm run test
npm run e2e
npm run lint
npm run build
```

### 前端一键验证

```bash
cd frontend
npm run test:all
```

### 后端测试

```bash
cd backend
pytest -q
```

目前已经验证通过的前端 E2E 场景包括：

1. 创建任务并直接模拟成功
2. 任务失败后重试再成功
3. 达到重试上限后显示友好错误并保持失败状态
4. 先预览执行计划，再触发真实执行并完成任务

---

## 当前技术方案

从实现角度看，NexusAI 当前采用的是“先跑通，再扩展”的 MVP 方案：

后端使用 FastAPI 作为 API 网关与服务承载层，Pydantic 负责模型校验；任务、Agent、事件和结果信息在运行时保存在内存中，并默认通过 JSON 文件做轻量持久化，便于快速演示和服务重启恢复；现在也支持通过环境变量切换到 SQLite 过渡存储（默认仍为 JSON）；消息流通过
API 记录与 WebSocket 推送结合；工作流、路由与共识能力通过服务层对象组织，为之后接入更复杂的 Agent 编排框架预留了空间。

为了支持演示准备，后端还提供了可选的启动种子加载（`NEXUSAI_SEED_ENABLED`）和可选的调试存储接口（`/api/debug/storage/*`，需显式开启 `NEXUSAI_DEBUG_API_ENABLED=true`）。

前端使用 Next.js App Router 组织页面，用 React 组件承载 Dashboard，使用 Tailwind CSS 做样式，React Flow 展示任务图。前端 API
客户端与 WebSocket 订阅逻辑已经拆分出来，后续继续扩展时不会影响整体结构。

---

## 当前限制

为了保持产品化迭代节奏，当前版本明确只覆盖 MVP 基线，不追求一次性到位的生产级能力。因此它仍有一些已知限制：

首先，仓库默认启动配置仍保留本地 JSON 路径以便开箱即跑，但产品化发布基线已完成 PostgreSQL cutover 证据闭环（详见 `backend/data/cutover-maintenance-report.json`）；其次，目前已有 `API key + role` 的 Phase A 鉴权，但尚未演进到完整 JWT / 用户体系；再次，虽然已提供真实 Agent 执行入口（`/execute`）并支持 OpenAI 兼容提供方，但默认演示仍建议保留模拟流程作为降级路径；最后，根目录旧版文档历史上曾有较多草稿与片段，当前应以本 README、
`backend/README.md`、`frontend/README.md` 以及实际代码行为为准。

这些限制不影响它作为产品化阶段可运行基线来验证多 Agent 协作中枢的核心价值；下一阶段仍应优先把 JSON 过渡层升级为 SQLite / PostgreSQL，并补统一配置体系、鉴权、安全策略、日志监控以及真实模型接入。

---

## 接下来可以继续做什么

如果继续往下推进，建议直接按“产品化优先级”执行：

### P0（产品基线必备，先做）

1. 固化一条 5-8 分钟演示脚本（首页总览 → 任务台创建 → 单任务工作区失败/重试/成功 → 智能体页解释协作）。
2. 为关键失败路径补齐用户可读错误提示（执行失败、重试上限、后端离线、WebSocket 中断）。
3. 继续补 E2E 稳定性场景（包括执行预览 + 执行、claim + handoff、冲突任务筛选）。

### P1（产品体验增强，其次做）

1. 增强可观测性展示（事件检索、事件回放、关键指标摘要）。
2. 补更多 Agent 模板与典型任务模板，提升“多角色协作”展示效果。
3. 优化任务结果呈现（结果摘要、共识解释、关键字段高亮）。

### P2（演进储备，最后做）

1. 持续优化 PostgreSQL 主存储（备份策略、容量规划、查询与索引优化）。
2. 引入统一配置、鉴权、安全策略与日志监控。
3. 将模拟执行进一步替换为真实 LLM 执行链路，并完善路由/仲裁策略。

---

## 相关文档

- 项目计划书：`prospectus.md`
- 架构说明：`docs/architecture.md`
- 协议说明：`docs/protocol.md`
- API 说明：`docs/api_spec.md`
- 用户使用文档：`docs/frontend/frontend_end_user_guide.md`
- 发布基线：`docs/release_baseline.md`
- 阶段状态报告：`FINAL_STATUS_REPORT.md`
- 文档语言规范：`docs/documentation_language_policy.md`
- 后端说明：`backend/README.md`
- 前端说明：`frontend/README.md`
- API 文档：启动后访问 `http://localhost:8000/docs`

---

## 一句话总结

**NexusAI 是一个面向产品化推进的多智能体协作中枢 MVP，它已经能够以可运行、可观测、可测试的方式展示任务分发、协作执行、失败恢复与共识决策的完整链路。
**
