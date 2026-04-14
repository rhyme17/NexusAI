# NexusAI 项目进度

最后更新时间：2026-04-08

## 当前进度总结

- 总体阶段：产品化执行（ACA）
- 当前状态：Step 1-6 完成；已进入 Phase B 准备阶段
- 当前完成度：约 100%（Phase A + 产品化收口）

## 已完成工作

### 2026-04-08

- 补充并核对产品化收口文档口径，确认 Step 5/Step 6 的状态边界（真实切库前不提前宣告完成）。
- 执行后端快速回归：`backend/tests/test_api.py` 中 health/agents 相关用例，结果 `6 passed`。
- 执行前端快速校验：`frontend` `npm run typecheck`，结果通过。
- 明确当前主阻塞点为 PostgreSQL 维护窗口 cutover 的生产化证据闭环。
- 增强迁移工具：`migrate_snapshot.py` 新增 `verify` 子命令，支持 import 前结构校验与结构化错误输出。
- 增强迁移防护：`app/services/migration.py` 增加快照结构校验，非法快照会在导入前失败并返回明确错误。
- 新增测试覆盖：`backend/tests/test_migration.py` 扩展为 3 个用例，验证 roundtrip、校验报错、非法导入拒绝。
- 执行迁移回归：`python -m pytest -q tests/test_migration.py`，结果 `3 passed`；`python migrate_snapshot.py verify --input .\data\not-exists.json` 错误路径验证通过。
- Step 1 性能检查：`python -m pytest -q tests/test_phase_a_perf.py -k "snapshot_migration"` -> `1 passed`。
- 新增 cutover 预演入口：`backend/rehearse_cutover.py`，支持一键执行 `export -> verify -> import` 并生成证据报告。
- 完成一次 Step 5 预演实操：`python rehearse_cutover.py` 返回 `status=ok`，`import.matches=true`。
- 预演证据落盘：`backend/data/cutover-rehearsal-report.json`，并同步到 `RELEASE_GATE_CHECKLIST.md` 与 `FINAL_STATUS_REPORT.md`。
- Step 2 功能检查：`python -m pytest -q tests/test_api.py -k "read_only_mode or api_auth_"` -> `7 passed`。
- Step 2 性能检查：`python -m pytest -q tests/test_phase_a_perf.py -k "task_create or task_events_with_auth"` -> `3 passed`。
- Step 3 功能检查：`python -m pytest -q tests/test_task_services.py -k "workflow_service_ or retry_exhausted"` -> `5 passed`。
- Step 3 性能检查：`python -m pytest -q tests/test_phase_a_perf.py -k "workflow_dag_generation or workflow_dispatch_cycle"` -> `1 passed`。
- 强化预演报告：`backend/rehearse_cutover.py` 新增 `checks/failure_reasons/timings` 字段与明确失败语义。
- 强化迁移契约校验：`migration.validate_runtime_snapshot` 新增 `attempt_history`、`consensus`、`metadata.decomposition.workflow_run/dag_nodes` 结构校验。
- 新增预演单测：`backend/tests/test_rehearse_cutover.py`（覆盖成功/失败分支）。
- 新增一键门禁：`backend/release_gate.py`（`quick/full` 配置，输出 `backend/data/release-gate-report.json`）。
- Step 4 功能检查：`python -m pytest -q tests/test_rehearse_cutover.py` -> `2 passed`；`python release_gate.py --profile quick` -> `status=ok`。
- Step 4 性能检查：`python -m pytest -q tests/test_phase_a_perf.py -k "task_create or snapshot_migration"` -> `3 passed`。
- 新增候选切换门禁 profile：`release_gate.py --profile cutover_candidate`（rehearsal + migration + API smoke + snapshot perf）。
- 预演新增预算能力：`rehearse_cutover.py --max-total-ms/--max-import-ms`，超预算会返回 `failed` 并给出 failure reasons。
- 新增门禁测试：`backend/tests/test_release_gate.py`（profile 存在性 + run_command 行为）。
- Step 5 功能检查：`python release_gate.py --profile cutover_candidate` -> `status=ok, passed_checks=4/4`。
- Step 5 性能检查：`python -m pytest -q tests/test_phase_a_perf.py -k "snapshot_migration"` -> `1 passed`。
- Step 6 功能检查：`python -m pytest -q tests/test_release_gate.py` -> `2 passed`。
- Step 6 性能检查：`python -m pytest -q tests/test_phase_a_perf.py -k "health_latency_budget or task_create_latency_budget"` -> `2 passed`。
- Step 5 真实维护窗口切换已执行：`export -> verify -> import`，`import.matches=true`，`counts={tasks:318,agents:8,tasks_with_events:323,events:2158}`。
- Step 5 API 校验：`/health`、`/api/agents`、`/api/tasks` 全部 `200`（PostgreSQL 后端）。
- Step 5 快速门禁：`python release_gate.py --profile quick`（PostgreSQL 配置）-> `status=ok, passed_checks=3/3`。
- 实操证据已落盘：`backend/data/cutover-maintenance-report.json`。
- `PRODUCTIZATION_PLAN_ACA.md` 已将 Step 5/6 收口为 `已完成`。
- 文档同步后功能复核：`python release_gate.py --profile quick`（PostgreSQL 配置）-> `status=ok, passed_checks=3/3`。
- 文档同步后性能复核：`python -m pytest -q tests/test_phase_a_perf.py -k "health_latency_budget or snapshot_migration"` -> `2 passed`。
- 修复测试脚本模块导入提示：`test_rehearse_cutover.py`、`test_release_gate.py` 改为 `importlib` 文件路径加载；复测 `5 passed`。
- Phase B 启动：完成基于 `prospectus.md` 的差距复盘，形成 5 周产品化后续计划（写入 `PRODUCTIZATION_PLAN_ACA.md`）。
- 新增协议契约测试：`backend/tests/test_protocol_contract.py`，锁定 `BusMessage` 核心结构与核心事件集合。
- 协议对齐补齐：`MessageType` 新增 `TaskReject`，并同步 `docs/protocol.md`、`backend/README.md` 事件清单。
- 发布门禁增强：`backend/release_gate.py` 的 `quick/full/cutover_candidate` 均纳入协议契约测试。
- Week 2 路由稳定化（第一批）已落地：`app/core/config.py` 新增 `resolve_router_policy`，支持环境变量 + `task.metadata.routing_policy` 覆盖。
- 路由解释契约增强：`app/services/router.py` 新增 `priority/policy/score_breakdown` 字段，并引入 `policy_version=v1`。
- 新增回归测试：`tests/test_phase_a_config.py`（router policy 解析）与 `tests/test_task_services.py`（路由稳定性/负载权重覆盖），并扩展 `tests/test_api.py` 路由解释断言。
- Week 2 校验：`python -m pytest -q tests/test_phase_a_config.py -k "router_policy"` -> `2 passed`；`python -m pytest -q tests/test_task_services.py -k "task_router_"` -> `3 passed`；`python -m pytest -q tests/test_api.py -k "test_task_contains_basic_decomposition_metadata"` -> `1 passed`。
- 快速门禁复核：`python release_gate.py --profile quick` -> `status=ok, passed_checks=4/4`。
- Week 3 调度可靠性（第一批）已落地：`workflow.py` 支持 `metadata.workflow_parallel_branches=true` 的并行分支 DAG（4 步模板下 `step_2/step_3` 可并行）。
- `requeue_task` 增加幂等保护：无失败节点时返回 `task_requeue_skipped` 事件，避免重复派发导致 attempt 误增。
- 新增恢复场景测试：`tests/test_json_persistence.py::test_workflow_recovery_continues_dispatch_after_store_reload`，验证重载后可继续推进 workflow。
- 运维配置补齐：`backend/.env.example` 新增 `NEXUSAI_ROUTER_*` 参数模板；`backend/README.md` 与 `docs/release_baseline.md` 同步路由策略配置说明。
- 发布门禁强化：`release_gate.py --profile full` 纳入 `router_policy` 与 `router_stability` 检查，并在报告中输出 `check_name/failed_check_name`。
- 门禁清单同步：`RELEASE_GATE_CHECKLIST.md` 已加入路由策略与路由稳定性检查命令。
- Week 3 校验：`python -m pytest -q tests/test_task_services.py -k "workflow_service_"` -> `6 passed`；`python -m pytest -q tests/test_json_persistence.py -k "workflow_recovery"` -> `1 passed`；`python -m pytest -q tests/test_release_gate.py` -> `3 passed`。
- Full 门禁实跑：`python release_gate.py --profile full` -> `status=ok, passed_checks=9/9`。
- Week 3 下一批完成：`workflow.py` 增加 `workflow_failure_policy`（`fail_fast`/`continue`），并在 `node_failed` 事件中返回 `failure_policy`。
- 并行失败恢复策略完成：在 `continue` 策略下，依赖失败节点的分支可解锁并继续派发；`fail_fast` 保持阻断。
- 事件序列回放测试补齐：新增 `test_workflow_event_sequence_replay_is_stable_after_bus_reload`，验证持久化后 `node_failed` 后仍可重放到后续 `node_dispatched`。
- Week 4 可解释性增强完成：新增冲突样例集 `backend/tests/fixtures/conflict_samples.json`，并增加共识 explanation 结构化稳定断言（`test_task_services.py`）。
- 仲裁 explanation 稳定断言增强：`test_api.py` 对 `judge_override/judge_unavailable` 路径增加关键字段集合断言。
- 发布回归固化完成：`release_gate.py` 新增 `--archive-history` 与 `--history-dir`，支持 full 门禁结果自动归档到 `backend/data/release-gate-history/`。
- 归档证据实跑：`python release_gate.py --profile full --archive-history` -> `status=ok, passed_checks=9/9`，归档 `backend/data/release-gate-history/release-gate-full-20260408T051541Z.json`。
- Week 4 下一批完成：扩展冲突样例集 `backend/tests/fixtures/conflict_samples.json`（等置信度/边界置信度/不同 proposal 分布），并新增 API 端到端回归 `test_consensus_conflict_samples_api_e2e`。
- 共识/仲裁回归增强：`test_task_services.py` 的冲突样例结构化 explanation 断言扩展到 4 组样例；`test_api.py` 对 Decision 事件 explanation 字段做稳定断言。
- Week 5 可观测性补强（第一批）完成：前端事件类型补齐 `TaskReject`，新增 `frontend/src/lib/api/event-observability.ts` 统一关键字段映射。
- Dashboard 映射一致性完成：`event-insights.tsx` 改为统一映射读取决策/失败字段；`event-stream.tsx` 新增 `TaskUpdate` 预览字段并统一非回放排序为按时间倒序。
- 回放一致性测试补齐：`frontend/src/components/event-stream.test.tsx` 新增无序输入排序断言；后端 `test_workflow_event_sequence_replay_is_stable_after_bus_reload` 保持通过。
- 发布回归持续执行：再次运行 `python release_gate.py --profile full --archive-history` -> `status=ok, passed_checks=9/9`，归档 `backend/data/release-gate-history/release-gate-full-20260408T052238Z.json`。
- 执行面板默认策略收口：`frontend/src/components/task-detail.tsx` 将执行回退默认改为关闭，并提示仅在手动启用时才允许真实执行失败后回退为模拟结果。
- 真实执行可用性提示完善：`frontend/src/components/task-detail.tsx` 新增用户 AI Key 状态提示；`backend/tests/test_api.py` 新增 `api_key` forwarding 回归，确认执行请求会把用户输入的 key 传入真实执行适配器。
- 修复真实执行崩溃：`agent_execution.py` 在 OpenAI client 初始化失败（含 `proxies` 参数不兼容）时改为抛出结构化 `E_EXECUTION_PROVIDER`，不再触发未处理 ASGI 异常。
- 依赖兼容性收口：`backend/requirements.txt` 将 `httpx` 固定为 `0.27.2`，避免与当前 `openai==1.51.2` 组合导致初始化报错。
- 新增回归测试：`backend/tests/test_agent_execution_service.py` 增加 client 初始化 TypeError 包装断言，覆盖依赖不兼容场景。

## 里程碑状态（对齐 PRODUCTIZATION_PLAN_ACA）

- ✅ Step 1：内部运维工作台边界收敛
- ✅ Step 2：DAG/Queue 元数据落地
- ✅ Step 3：持久化调度器 MVP
- ✅ Step 4：运维工作台 UI 承接
- ✅ Step 5：停机迁移切换完成（维护窗口实操 + 一致性校验）
- ✅ Step 6：发布门禁与基线文档收口完成

## 下一步计划（按优先级）

1. Week 5 下一批：把 `event-observability` 映射扩展到更多事件（`TaskRetryExhausted`、`ConflictNotice`）并补前端快照测试。
2. Week 6 预备：统一前后端事件口径文档（字段级协议表）并补 `docs/protocol.md` 示例。
3. 继续执行发布回归：每次变更后运行 `release_gate.py --profile full --archive-history` 并归档报告。

## 关键风险与注意事项

- 生产/内测环境必须保持 `NEXUSAI_STORAGE_BACKEND=postgres` 与 `NEXUSAI_STORAGE_FALLBACK_ON_ERROR=false`，避免运行时漂移。
- 仍需定期执行回滚演练，确保异常情况下可在维护窗口内恢复服务。
- 仓库本地默认 JSON 仅用于开发便利，不应直接作为发布环境配置。


