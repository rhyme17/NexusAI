# NexusAI 发布门禁清单

更新日期：2026-04-08

本清单用于把当前仓库从“可运行 MVP”推进到“可控发布”的状态。

配套基线文档：`docs/release_baseline.md`

---

## 1. 后端功能门禁

必须通过：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python -m pytest -q tests/test_api.py -k "api_auth_ or role_guard or decomposition"
python -m pytest -q tests/test_phase_a_config.py -k "router_policy"
python -m pytest -q tests/test_task_services.py -k "task_router_"
python -m pytest -q tests/test_task_services.py -k "workflow_service_ or retry_exhausted"
python -m pytest -q tests/test_sqlite_store.py -k "sqlite_store or task_api_can_run_with_sqlite_store_override"
python -m pytest -q tests/test_websocket.py -k "retry_event_after_failure or retry_exhausted_event"
python -m pytest -q tests/test_migration.py
```

---

## 2. 后端性能门禁

必须通过：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python -m pytest -q tests/test_phase_a_perf.py
```

覆盖内容包括：

- 健康检查延迟
- 任务创建延迟
- 启用鉴权后的任务创建延迟
- 启用鉴权后的事件读取延迟
- 工作流 DAG 生成延迟
- 工作流调度循环延迟
- 快照迁移延迟

---

## 3. 前端门禁

必须通过：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\frontend"
npm run typecheck
npm run test
npm run e2e
```

当前重点覆盖：

- 后端 API key 注入
- 授权错误提示
- DAG / queue runtime 展示
- 执行预览与执行
- 失败重试提示
- claim / handoff 事件流
- 后端离线可读提示

---

## 4. 运维与迁移门禁

切换到 PostgreSQL 前必须确认：

- `POSTGRES_CUTOVER_RUNBOOK.md` 已过一遍 dry-run
- `migrate_snapshot.py export` 可执行
- `migrate_snapshot.py verify` 可执行（并返回 `status=valid`）
- `migrate_snapshot.py import` 可执行
- import 结果 `matches=true`
- 回滚文件已备份

---

## 5. 当前建议发布顺序

1. 在维护窗口执行 Step 5 PostgreSQL 主切换
2. 确认 `matches=true`，并关闭 fallback
3. 以 `docs/release_baseline.md` 为准收口默认配置、角色矩阵和回滚标准
4. 更新根 README / `docs/archive/FINAL_STATUS_REPORT.md` / 相关 docs
5. 再宣布进入“产品化内测”而非“原型演练阶段”

补充：可使用 `python backend/release_gate.py --profile quick` 做快速门禁回归，并保留 `backend/data/release-gate-report.json` 作为证据。
补充：建议每次变更后执行 `python backend/release_gate.py --profile full --archive-history`，并保留 `backend/data/release-gate-history/` 归档。

---

## 6. 当前验证记录（2026-04-07）

- Backend release-gate 命令：已通过
- Frontend `typecheck` / `vitest` / `playwright`：已通过
- 当前仓库状态：**历史记录（已归档）**

## 7. 增量验证记录（2026-04-08）

- 后端快速回归：`python -m pytest -q tests/test_api.py -k "health or agents"` -> `6 passed`
- 前端快速校验：`npm run typecheck` -> 通过
- 阶段状态报告：`docs/archive/FINAL_STATUS_REPORT.md`

## 8. Step 5 预演证据模板（维护窗口前）

- 执行时间：`YYYY-MM-DD HH:mm`
- 执行环境：`local/staging`
- 执行人：`<name>`
- 命令：
  - `python migrate_snapshot.py export --output <snapshot>`
  - `python migrate_snapshot.py verify --input <snapshot>`
  - `python migrate_snapshot.py import --input <snapshot>`
- 关键输出：
  - `export.status=exported`
  - `verify.status=valid`
  - `import.status=imported`
  - `import.matches=true`
- 结论：`pass/fail`

建议补充候选切换门禁：

- 命令：`python release_gate.py --profile cutover_candidate`
- 通过标准：
  - rehearsal `status=ok`
  - migration tests 通过
  - API smoke（health/agents）通过
  - snapshot_migration perf 通过

## 9. Step 5 预演实操记录（2026-04-08）

- 执行时间：`2026-04-08`
- 执行环境：`local`
- 命令：`python rehearse_cutover.py`
- 输出摘要：
  - `status=ok`
  - `export.counts={tasks:310,agents:8,tasks_with_events:315,events:2038}`
  - `verify.status=valid`
  - `import.status=imported`
  - `import.matches=true`
- 证据文件：`backend/data/cutover-rehearsal-report.json`

## 10. Step 6 快速门禁记录（2026-04-08）

- 命令：`python release_gate.py --profile quick`
- 输出摘要：`status=ok`，`passed_checks=3/3`
- 证据文件：`backend/data/release-gate-report.json`

## 11. 候选切换门禁记录（2026-04-08）

- 命令：`python release_gate.py --profile cutover_candidate`
- 输出摘要：`status=ok`，`passed_checks=4/4`
- 证据文件：`backend/data/release-gate-report.json`

## 12. Step 5 维护窗口实操记录（2026-04-08）

- 执行环境：`local maintenance window / postgres`
- 目标配置：
  - `NEXUSAI_STORAGE_BACKEND=postgres`
  - `NEXUSAI_POSTGRES_DSN=postgresql://nexus:***@localhost:55432/nexusai`
  - `NEXUSAI_STORAGE_FALLBACK_ON_ERROR=false`
- 执行命令（按顺序）：
  - `python migrate_snapshot.py export --output .\data\cutover-maintenance-snapshot.json`
  - `python migrate_snapshot.py verify --input .\data\cutover-maintenance-snapshot.json`
  - `python migrate_snapshot.py import --input .\data\cutover-maintenance-snapshot.json`
  - API smoke：`/health`、`/api/agents`、`/api/tasks` 均 `200`
  - `python release_gate.py --profile quick`
- 关键输出：
  - `export.status=exported`
  - `verify.status=valid`
  - `import.status=imported`
  - `import.matches=true`
  - `counts={tasks:318,agents:8,tasks_with_events:323,events:2158}`
  - `release_gate_quick.status=ok`，`passed_checks=3/3`
- 证据文件：
  - `backend/data/cutover-maintenance-snapshot.json`
  - `backend/data/cutover-maintenance-report.json`
  - `backend/data/release-gate-report.json`
- 结论：`Step 5 completed`


