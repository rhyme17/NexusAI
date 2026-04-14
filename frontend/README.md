# NexusAI 前端 MVP

这是服务于 NexusAI FastAPI 后端的 Next.js 14 + React + TypeScript + Tailwind Dashboard。

## 当前信息架构

- `/`：总览首页（健康状态、关键计数、焦点任务、最近任务）
- `/tasks`：任务工作区，支持创建、筛选和列表浏览
- `/tasks/[taskId]`：单任务工作区，聚合执行、重试、事件、拆解和共识信息
- `/agents`：智能体工作区，展示角色/状态/技能并高亮任务相关智能体

## 手册入口

- 用户手册：`docs/user_manual.md`
- 开发与运维手册：`docs/developer_manual.md`

## 当前 MVP 能力

- **系统总览**：展示后端健康状态、任务数、智能体数、焦点任务和最近任务入口
- **任务操作**：支持创建任务、任务筛选/列表浏览，并可深链进入单任务工作区
- **归属操作**：支持智能体认领任务与任务交接
- **共识可视化**：提供 proposal 列表与 proposal-vs-decision 对比表
- **事件可观测性**：支持任务事件历史、WebSocket 实时流、按类型/时间范围过滤
- **工作流可视化**：支持拆解详情和 React Flow DAG 图展示
- **工作流运行态可视化**：任务概览中展示 `workflow_run`、`dispatch_state`、`ready_queue` 以及各节点派发状态，便于内部运维观察
- **智能体工作区**：展示角色/状态/技能，并高亮当前任务的参与者
- **双语体验**：默认中文界面，并支持页内中英切换
- **Anthropic 风格视觉系统**：采用温暖中性色、衬线 + 无衬线字体搭配，以及偏编辑型的信息层级
- **执行控制面板**：可配置 `single` / `pipeline` / `parallel`，预览执行步骤/事件/告警，再触发真实执行
- **可解释性面板**：在单任务工作区展示 routing explanation、consensus explanation、arbitration explanation
- **用户 API Key 支持**：侧边栏内置全局 key 窗口，保存用户 `MODELSCOPE_ACCESS_TOKEN`；任务执行面板不再要求每个任务单独输入 key
- **后端 API Key 支持**：侧边栏可本地保存后端 `X-API-Key`，并自动附加到受保护的后端请求
- **智能体注册入口**：`/agents` 页面内置注册表单（name/role/skills）
- **服务端数据控制**：侧边栏支持清空事件 / 清空任务+事件 / 重置并恢复 seed（需后端开启 debug）

## 5-8 分钟演示脚本（以前端为主）

1. 打开 `/`，展示健康状态和关键计数。
2. 打开 `/tasks`，创建一个任务，并跳转进入 `/tasks/[taskId]`。
3. 在执行页签中依次点击：`Preview Execution` -> `Execute`。
4. 触发 `Simulate Failure`，再执行 `Retry Task`，最后触发 `Simulate Success`。
5. 在总览/协作相关页签中说明：
   - routing explanation（为什么选择这些智能体）
   - consensus explanation（为什么选择该结果）
   - arbitration explanation（如果走 judge 仲裁路径）
6. 打开 `/agents`，用角色/状态/技能视图完成收尾。

演示前可选重置（需后端启用 debug API）：

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/debug/storage/clear?restore_seed=true"
```

当后端开启 debug API 后，左侧边栏 `Server data` 区域也提供应用内重置控制。

## 前置条件

- Node.js 18+
- 后端运行在 `http://localhost:8000`

## 本地开发

1. 安装依赖。
2. 复制环境变量模板。
3. 启动开发服务器。

```bash
npm install
copy .env.local.example .env.local
npm run dev
```

打开 `http://localhost:3000`。

## 后端启动参考

```bash
cd ../backend
python -m uvicorn app.main:app --reload --port 8000
```

## 常用脚本

```bash
npm run dev
npm run typecheck
npm run test
npm run test:all
npm run e2e
npm run lint
npm run build
```

## E2E 冒烟测试（Playwright）

要求本地后端和前端都可访问。

可选环境变量：

- `PLAYWRIGHT_BASE_URL`（默认 `http://127.0.0.1:3000`）
- `PLAYWRIGHT_BACKEND_URL`（默认 `http://localhost:8000`）

```bash
# 后端终端
cd ../backend
python -m uvicorn app.main:app --reload --port 8000

# 前端终端
npm install
npx playwright install chromium
npm run e2e
```

当前冒烟路径：

- 打开 `/tasks`
- 通过 UI 创建任务（自动跳转到 `/tasks/[taskId]`）
- 触发 “Simulate Success”
- 断言任务变为 `completed`

补充重试路径：

- 在 `/tasks` 创建任务
- 触发 “Simulate Failure”
- 重试任务
- 触发 “Simulate Success”
- 断言任务重新回到 `completed`

重试耗尽路径：

- 创建带有 `metadata.max_retries=0` 的任务（由 E2E seed 提供）
- 打开 `/tasks/[taskId]`
- 触发 “Simulate Failure”
- 点击 “Retry Task”
- 断言出现本地化重试上限提示，且任务仍保持 `failed`

执行预览路径：

- 在 `/tasks` 创建任务
- 在 `/tasks/[taskId]` 打开执行预览面板
- 触发 “Preview Execution”
- 触发 “Execute”
- 断言任务变为 `completed`

协作路径：

- 在 `/tasks` 创建任务
- 由一个智能体 claim，再 handoff 给另一个智能体
- 断言事件流中出现 `TaskClaim` 与 `TaskHandoff`

冲突筛选路径：

- 通过后端 API seed 一个正常任务和一个冲突任务
- 在 `/tasks` 打开 “only conflict tasks” 过滤器
- 断言界面仅剩冲突任务那一行

后端离线路径：

- 在浏览器内模拟任务列表请求失败
- 打开 `/tasks`
- 断言页面显示本地化、可读的兜底提示

## 已知 MVP 限制

- 后端仓库默认可使用 JSON 快照以便本地快速启动，但发布基线已支持并验证 PostgreSQL 主存储切换
- 前端虽然已支持后端 API Key 输入，但完整的 JWT 会话与更细粒度的角色体验仍在推进中
- UI 默认假定后端路由定义位于 `backend/app/api/*.py`

