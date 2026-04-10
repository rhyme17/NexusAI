# NexusAI 阶段状态报告（产品化收口）

更新日期：2026-04-08

## 1) 结论

NexusAI 已完成产品化计划（ACA）中的 Step 1-6。
Step 5 PostgreSQL 维护窗口切换已完成，并通过 `matches=true` 与 API/门禁校验闭环。

当前建议对外口径：

> 项目已完成产品化封板，可按内部发布基线运行（默认部署基线为 PostgreSQL + fallback 关闭）。

## 2) 对齐 PRODUCTIZATION_PLAN_ACA 的执行状态

- Step 1（内部运维工作台边界）：已完成
- Step 2（DAG/Queue 领域模型）：已完成
- Step 3（持久化队列与 DAG 调度器 MVP）：已完成
- Step 4（前端运维工作台）：已完成
- Step 5（PostgreSQL 停机迁移切换）：已完成（维护窗口实操完成）
- Step 6（发布封板与门槛）：已完成（门禁、基线、回滚文档收口完成）

## 3) 已完成验证证据

- 后端快速回归（2026-04-08）：
  - 命令：`python -m pytest -q tests/test_api.py -k "health or agents"`
  - 结果：`6 passed, 65 deselected`
- 前端快速校验（2026-04-08）：
  - 命令：`npm run typecheck`
  - 结果：通过
- 已有完整门禁基线文档：
  - `RELEASE_GATE_CHECKLIST.md`
  - `docs/release_baseline.md`
- Step 5 预演证据（2026-04-08）：
  - 命令：`python rehearse_cutover.py`
  - 结果：`status=ok`，`verify.status=valid`，`import.matches=true`
  - 证据：`backend/data/cutover-rehearsal-report.json`
- Step 6 快速门禁自动化（2026-04-08）：
  - 命令：`python release_gate.py --profile quick`
  - 结果：`status=ok`，`passed_checks=3/3`
  - 证据：`backend/data/release-gate-report.json`
- Step 5 候选切换门禁（2026-04-08）：
  - 命令：`python release_gate.py --profile cutover_candidate`
  - 结果：`status=ok`，`passed_checks=4/4`
  - 证据：`backend/data/release-gate-report.json`
- Step 5 真实维护窗口切换（2026-04-08）：
  - 命令：`export -> verify -> import -> API smoke -> release_gate quick`
  - 结果：`import.matches=true`，`counts={tasks:318,agents:8,tasks_with_events:323,events:2158}`，`release_gate_quick.status=ok`
  - 证据：`backend/data/cutover-maintenance-report.json`

## 4) Step 5 实操完成标准（必须全部满足）

1. 维护窗口开启，写入冻结（只读模式）。
2. 旧存储 snapshot 成功导出。
3. snapshot 成功导入 PostgreSQL。
4. 校验结果 `matches=true`。
5. 关键对象一致：tasks / agents / attempts / consensus / workflow metadata。
6. 切换到 `NEXUSAI_STORAGE_BACKEND=postgres` 且 `NEXUSAI_STORAGE_FALLBACK_ON_ERROR=false`。
7. 恢复写入后健康检查与关键 API 正常。

## 5) 风险与回滚基线

- 触发回滚条件：import 失败、`matches=false`、关键 counts 不一致、核心 API 异常。
- 回滚策略：立即进入只读，恢复旧配置与备份数据，再重启并验证 `/health`、`/api/tasks`、`/api/agents`。
- 参考文档：`backend/POSTGRES_CUTOVER_RUNBOOK.md`、`docs/release_baseline.md`。

## 6) 下一步执行清单

1. 进入 Phase B：围绕队列容量、调度可靠性、失败恢复自动化推进。
2. 以 `release_gate.py --profile full` 作为变更后固定回归门禁。
3. 按季度维护 cutover runbook 和回滚演练记录，保持迁移能力常态化。

