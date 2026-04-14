# NexusAI 产品化执行计划（ACA）

更新日期：2026-04-08  
策略选择：**A / C / A**

- **A**：优先面向内部运维/内部可用场景，而非开放平台
- **C**：PostgreSQL 采用**全量停机迁移切换**，不做长期双写
- **A**：Phase B 优先推进**队列 + DAG 执行器**

---

## 0. 当前状态判断

结合 `prospectus.md`、现有代码与测试现状，NexusAI 当前已经具备：

- 多 Agent 协作 MVP 主链路
- 任务创建 / 状态推进 / 重试 / 共识 / 事件流
- Dashboard 基础运维视图
- Phase A 基础安全：`API key + role`
- 可选 `json / sqlite / postgres(stage 1)` 存储切换

但距离“产品化”仍有明显差距：

1. 仍以演示思维为主，缺少内部运维产品边界定义
2. PostgreSQL 仅完成 Stage 1 backend 入口，缺少迁移 runbook
3. Workflow 仍是线性 placeholder，未形成真正的 DAG 调度闭环
4. 前端尚未完整承接后端授权模型
5. 缺少发布门槛、运维手册、回滚标准和容量基线

---

## Step 1：收敛为“内部运维工作台”产品

### 目标
把产品目标从“早期多 Agent Demo”收敛为“内部运维台 / 内部协作中枢”，冻结第一阶段产品边界。

### 最小交付物
- 明确核心使用者：平台运营、研发验证、演示准备人员
- 核心路径只保留：
  - 创建任务
  - 执行任务 / 预览执行
  - 查看事件与共识
  - 重试 / claim / handoff
  - 调试清理与恢复 seed
  - 审计追踪
- 非本阶段目标：
  - 多租户
  - 第三方开放平台
  - Agent Marketplace
  - 复杂计费与 SLA

### 验收标准
- 后端存在角色访问矩阵测试
- 前端支持配置 backend API key
- 前端对 401 / 403 给出用户可读提示
- Phase A 性能测试增加“auth enabled”基线

### 回滚点
如果角色体验影响现有 demo 路径，回滚到“仅后端鉴权、前端不强依赖 API key”的状态。

---

## Step 2：在存储契约层引入 DAG / Queue 领域模型

### 目标
在不打破现有任务 API 的情况下，为真正的 DAG 执行器建立可持久化的元数据结构。

### 最小交付物
新增并统一以下概念：

- `workflow_run`
- `dag_nodes`
- `dag_edges`
- `dispatch_state`
- `ready_queue`
- `node_attempts`

第一阶段允许继续存放在 `task.metadata` 或附属模型中，但要保证三种 backend 一致读写。

### 验收标准
- `StoreContract` 对 DAG 元数据具备统一接口
- `json` / `sqlite` / `postgres` 至少在测试中表现一致
- 任务创建后可生成结构化 DAG 描述，而不只是线性 decomposition

### 回滚点
保留现有 `decomposition` 线性结构，把 DAG 字段设为可选附加信息。

---

## Step 3：落地应用内持久化队列 + DAG 调度器

### 目标
把现有线性 workflow 演进为可恢复、可观测的内部调度器。

### 最小交付物
- 任务入队
- 节点依赖判定
- ready queue 派发
- 节点成功/失败推进
- 失败节点重试
- 父任务汇总
- 调度事件落盘并可回放

### 验收标准
- 支持串行 DAG
- 支持简单并行分支
- 支持失败后继续/失败即停策略
- 重启后能从存储恢复调度状态

### 回滚点
保留现有 `enqueue_task()` 线性逻辑，并通过配置关闭 DAG 调度器。

---

## Step 4：前端升级为运维工作台

### 目标
让前端不只是演示 UI，而是能承接内部值守、排障和迁移过程的操作台。

### 最小交付物
- backend API key 配置入口
- 角色受限时的只读/禁用提示
- DAG 节点状态面板
- queue / dispatch 状态摘要
- 失败节点人工重试入口
- 停机迁移只读 banner

### 验收标准
- `/tasks/[taskId]` 能看见 DAG 节点进度
- 管理能力在无权限时明确禁用
- 至少 1 条 E2E 路径覆盖“失败节点 -> 人工恢复”

### 回滚点
前端先退回只读展示 DAG 摘要卡，不开放复杂控制入口。

---

## Step 5：按停机迁移策略切换到 PostgreSQL 主存储

### 目标
完成从 JSON / SQLite 过渡层到 PostgreSQL 的一次性切换。

### 迁移策略（C）
1. 宣布维护窗口
2. 冻结写入
3. 导出当前 snapshot
4. 导入 PostgreSQL
5. 校验 counts / IDs / attempts / consensus / workflow metadata
6. 切换 `NEXUSAI_STORAGE_BACKEND=postgres`
7. 关闭 fallback
8. 重新开放服务

### 最小交付物
- 导出 / 导入脚本或管理命令
- 迁移校验清单
- 回滚 runbook

### 验收标准
- Postgres 成为默认主存储
- fallback 默认关闭
- 迁移校验通过后再放开写入

### 回滚点
保留切换前 JSON / SQLite 快照与旧配置，一旦校验失败立即回滚。

---

## Step 6：形成发布封板与产品化门槛

### 目标
把“能跑”升级为“可发布、可回滚、可验收”。

### 最小交付物
- 发布检查表
- 环境变量基线
- 性能基线
- 角色权限矩阵
- 迁移手册
- 故障回滚手册
- 默认生产配置建议

### 发布门槛
后端至少通过：

- API 功能回归
- StoreContract 一致性测试
- WebSocket 事件测试
- 迁移测试
- 性能基线测试

前端至少通过：

- typecheck
- vitest
- 核心 E2E
- 授权/只读/失败恢复路径验证

---

## 测试门禁建议

### 功能测试
- `backend/tests/test_api.py`
- `backend/tests/test_task_services.py`
- `backend/tests/test_sqlite_store.py`
- 未来补 `backend/tests/test_postgres_store.py`
- `backend/tests/test_websocket.py`
- `frontend/src/**/*.test.tsx`
- `frontend/tests/e2e/*`

### 性能测试
建议保留并扩展：

- 健康检查平均耗时
- 创建任务平均耗时
- 读取任务详情平均耗时
- 读取事件历史平均耗时
- DAG 生成耗时
- DAG 调度首节点启动耗时
- 前端任务详情页（大事件流 + 多节点）渲染耗时

---

## 本周执行顺序

1. **Step 1 完成**：前后端承接 backend API key + role 体验，补功能/性能测试
2. **Step 2 起草并落地最小 DAG 元数据结构**
3. **Step 3 实现应用内持久化调度器 MVP**
4. **Step 4 补前端 DAG/queue 运维视图**
5. **Step 5 准备停机迁移 runbook 与工具**
6. **Step 6 收口发布门槛与状态文档**

---

## 当前执行状态

- [x] Phase A：`API key + role`
- [x] Phase A：敏感接口角色门禁（`debug clear`）
- [x] Phase A：PostgreSQL Stage 1 backend 入口 + fallback
- [x] Step 1：内部运维产品边界与前端 auth 体验对齐
- [x] Step 2：DAG / queue 元数据统一
- [x] Step 3：持久化调度器 MVP
- [x] Step 4：运维工作台 UI
- [x] Step 5：停机迁移切换（已完成维护窗口实操：`export -> verify -> import`，`matches=true`）
- [x] Step 6：发布封板（发布门禁与基线文档收口完成，并沉淀可审计证据）

---

## Phase B（后续 5 周产品化计划）

### Week 1：协议契约收敛与门禁化
- 目标：锁定消息协议，避免后续路由/DAG/仲裁改造引入协议漂移。
- 交付：新增 `tests/test_protocol_contract.py`；`release_gate.py` 三个 profile 纳入协议契约检查。
- 验收：`python release_gate.py --profile quick` 通过且报告包含协议契约检查。
- 风险：历史事件兼容性；通过“协议新增向后兼容、删除需迁移”原则控制。

### Week 2：Task Router 稳定化
- 目标：路由策略可解释、可复现，减少同输入不同分配。
- 交付：补充优先级/负载权重配置与路由解释字段稳定性测试。
- 验收：同输入/同 agent 快照下 `selected_agent_ids` 稳定。
- 风险：路由策略改动影响历史 Demo 预期。

### Week 3：DAG 调度可靠性增强
- 目标：提升并行分支、失败恢复、重启恢复的一致性。
- 交付：补 `dispatch_ready_nodes` 并行分支与 `requeue` 幂等回归测试。
- 验收：故障恢复场景可重复通过测试。
- 风险：状态机边界变复杂，需严格事件序列测试。

### Week 4：冲突仲裁可解释性强化
- 目标：把 `consensus/arbitration` 从“能用”提升为“可审计可解释”。
- 交付：补冲突样例集（highest_confidence / majority_vote / judge），统一解释字段。
- 验收：冲突样例可重放，决策理由结构稳定。
- 风险：策略切换导致结果与旧版本不一致。

### Week 5：可观测与发布回归闭环
- 目标：把任务事件洞察、失败恢复路径纳入 release gate 与运维基线。
- 交付：扩展 `release_gate.py --profile full` 的稳定性检查并固化报告归档。
- 验收：每次变更可产出可比较的门禁报告与关键指标趋势。
- 风险：前后端指标口径不一致，需统一定义。



