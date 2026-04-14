# NexusAI 发布基线（Step 6）

更新日期：2026-04-08

> 本文档用于承接 `docs/archive/PRODUCTIZATION_PLAN_ACA.md` 中的 **Step 6：形成发布封板与产品化门槛**。
> 
> 当前判断：
> - **Step 1-4 已完成**
> - **Step 5 已完成维护窗口切换（`matches=true`）**
> - **Step 6 已完成 release hardening / gate verification 收口**

---

## 1. 当前发布判断

NexusAI 已经从“可演示”推进到“可封板验证”的状态。当前仓库已经具备：

- 后端功能门禁、迁移测试、性能基线测试
- 前端 typecheck、Vitest 与核心 Playwright E2E
- 停机迁移 runbook、snapshot export/import 工具
- 只读维护模式与 Dashboard 只读提示
- API key + role 的 Phase A 权限承接

当前建议状态为：

- **Step 5：已完成维护窗口 cutover**
- **Step 6：已完成发布封板收口**

---

## 2. 已验证的发布门禁

### 后端门禁

已验证命令：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python -m pytest -q tests/test_api.py -k "api_auth_ or role_guard or decomposition"
python -m pytest -q tests/test_task_services.py -k "workflow_service_ or retry_exhausted"
python -m pytest -q tests/test_phase_a_config.py -k "router_policy"
python -m pytest -q tests/test_task_services.py -k "task_router_"
python -m pytest -q tests/test_sqlite_store.py -k "sqlite_store or task_api_can_run_with_sqlite_store_override"
python -m pytest -q tests/test_websocket.py -k "retry_event_after_failure or retry_exhausted_event"
python -m pytest -q tests/test_migration.py
python -m pytest -q tests/test_phase_a_perf.py
```

当前结果：**全部通过**。

补充：可使用 `python backend/release_gate.py --profile quick` 执行快速门禁并生成 `backend/data/release-gate-report.json` 作为预演证据。
补充：可使用 `python backend/release_gate.py --profile cutover_candidate` 执行候选切换门禁（rehearsal + migration + API smoke + perf）。
补充：建议在日常回归中使用 `python backend/release_gate.py --profile full --archive-history` 生成历史归档证据。

### 前端门禁

已验证命令：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\frontend"
npm run typecheck
npm run test
npm run e2e
```

当前结果：**全部通过**。

---

## 3. 环境变量基线

### 3.1 本地演示基线

适用于 demo / 本地开发：

| 变量 | 建议值 | 说明 |
|---|---|---|
| `NEXUSAI_STORAGE_BACKEND` | `json` | 保持零依赖演示路径 |
| `NEXUSAI_STORAGE_FALLBACK_ON_ERROR` | `true` | 降低本地环境失败概率 |
| `NEXUSAI_DEBUG_API_ENABLED` | `false` / 按需打开 | 演示重置前可临时开启 |
| `NEXUSAI_SEED_ENABLED` | `false` / 按需打开 | 仅在准备演示基线时使用 |
| `NEXUSAI_API_AUTH_ENABLED` | `false` / 可选 | 演示默认可关闭，内测建议开启 |
| `NEXUSAI_READ_ONLY_MODE` | `false` | 非维护窗口关闭 |

### 3.2 内部发布基线

适用于 Step 5 cutover 完成后的内部环境：

| 变量 | 建议值 | 说明 |
|---|---|---|
| `NEXUSAI_STORAGE_BACKEND` | `postgres` | PostgreSQL 作为主存储 |
| `NEXUSAI_POSTGRES_DSN` | 必填 | 指向正式内部数据库 |
| `NEXUSAI_STORAGE_FALLBACK_ON_ERROR` | `false` | cutover 后默认关闭 fallback |
| `NEXUSAI_STORAGE_FALLBACK_BACKEND` | 不设置或仅作回滚预案 | 正常运行时不依赖 |
| `NEXUSAI_API_AUTH_ENABLED` | `true` | 内部发布默认开启 |
| `NEXUSAI_API_KEYS` | 必填 | 至少准备 admin / operator / viewer |
| `NEXUSAI_API_KEY_ROLES` | 必填 | 固化角色映射 |
| `NEXUSAI_API_AUTH_DEFAULT_ROLE` | `viewer` | 未映射 key 默认只读 |
| `NEXUSAI_DEBUG_API_ENABLED` | `false` | 发布态默认关闭 |
| `NEXUSAI_SEED_ENABLED` | `false` | 发布态不自动导入 seed |
| `NEXUSAI_READ_ONLY_MODE` | `false` | 仅维护窗口开启 |
| `NEXUSAI_EVENT_HISTORY_MAX` | `2000` 或更高 | 视任务/事件量调整 |
| `NEXUSAI_AGENT_EXECUTION_FALLBACK` | `simulate` 或 `fail` | 演示优先可保留 `simulate` |
| `NEXUSAI_ROUTER_SKILL_WEIGHT` | `100` | 路由技能匹配权重 |
| `NEXUSAI_ROUTER_STATUS_WEIGHT` | `10` | 路由状态权重 |
| `NEXUSAI_ROUTER_LOAD_PENALTY` | `1` | 路由负载惩罚系数 |
| `NEXUSAI_ROUTER_PRIORITY_STATUS_BONUS_*` | `low=0, medium=2, high=6` | 不同优先级的状态加权增益 |

---

## 4. 角色权限矩阵（Phase A）

| 能力 | admin | operator | viewer |
|---|---:|---:|---:|
| 查看健康状态 / Swagger | ✅ | ✅ | ✅ |
| 查看任务 / 详情 / 事件 / 共识 | ✅ | ✅ | ✅ |
| 创建任务 | ✅ | ✅ | 视部署策略而定 |
| simulate / execute / retry | ✅ | ✅ | ❌ |
| claim / handoff | ✅ | ✅ | ❌ |
| Debug clear / restore seed | ✅ | ❌ | ❌ |
| 维护窗口切换与回滚执行 | ✅ | 协助 | ❌ |

说明：

- 当前代码中已明确验证的强门禁点是 `debug clear` 的 `admin` 要求。
- 对于“viewer 是否允许创建任务”，建议内部环境按保守策略处理；若对值守台采用只读观察模型，可在网关层或后续角色矩阵继续收紧。

---

## 5. Step 5 -> Step 6 的实操闭环记录

已完成的 Step 5 实操项：

1. 按 `backend/POSTGRES_CUTOVER_RUNBOOK.md` 执行维护窗口
2. 导出 snapshot
3. 导入 PostgreSQL
4. 校验 `matches=true`
5. 校验 task / agent / attempts / consensus / workflow metadata
6. 切换为 `NEXUSAI_STORAGE_BACKEND=postgres`
7. 确认 `NEXUSAI_STORAGE_FALLBACK_ON_ERROR=false`
8. 放开写入并观察健康状态

执行结果：`import.matches=true`，并完成 `/health`、`/api/tasks`、`/api/agents` API smoke 及 `release_gate.py --profile quick` 校验。
证据文件：`backend/data/cutover-maintenance-report.json`。

---

## 6. 故障回滚基线

### 6.1 PostgreSQL cutover 回滚

若出现以下任一情况，应立即回滚：

- import 失败
- `matches=false`
- counts 不一致
- 关键任务丢失
- workflow metadata 缺失
- 服务恢复后核心 API 大面积异常

### 6.2 回滚步骤

```powershell
# 1) 重新进入冻结写入 / 维护模式
$env:NEXUSAI_READ_ONLY_MODE = "true"

# 2) 恢复旧后端配置（json 或 sqlite）
$env:NEXUSAI_STORAGE_BACKEND = "json"
$env:NEXUSAI_STORAGE_FALLBACK_ON_ERROR = "true"

# 3) 恢复数据目录 / sqlite 文件备份
# 4) 重启后端
# 5) 校验 /health、/api/tasks、/api/agents
```

说明：

- 发布前必须保留切换前 snapshot 与旧配置。
- 回滚后再开放写入，不要在未校验完成前恢复前端写操作。

---

## 7. 默认发布建议

### 当前仓库默认值

为了保证仓库开箱即跑，代码默认仍保持：

- `storage_backend=json`
- `fallback_on_error=true`
- `read_only=false`

这适合开发和演示，但**不是 Step 5 cutover 后的正式内部发布默认值**。

### 内部发布推荐值

推荐在环境文件或部署平台中明确覆盖：

```dotenv
NEXUSAI_STORAGE_BACKEND=postgres
NEXUSAI_POSTGRES_DSN=postgresql://user:password@host:5432/nexusai
NEXUSAI_STORAGE_FALLBACK_ON_ERROR=false
NEXUSAI_API_AUTH_ENABLED=true
NEXUSAI_API_KEYS=admin-key,operator-key,viewer-key
NEXUSAI_API_KEY_ROLES=admin-key:admin,operator-key:operator,viewer-key:viewer
NEXUSAI_API_AUTH_DEFAULT_ROLE=viewer
NEXUSAI_DEBUG_API_ENABLED=false
NEXUSAI_SEED_ENABLED=false
NEXUSAI_READ_ONLY_MODE=false
```

---

## 8. 当前结论

截至 2026-04-08：

- Step 6 所需的**发布门禁、环境基线、角色矩阵、回滚建议、默认配置建议**已经在仓库中形成可执行文档
- 后端与前端发布门禁已完成一轮实际验证
- 真实 PostgreSQL cutover 维护窗口执行已完成，并通过一致性与门禁验证

因此当前可对外使用如下表述：

> **NexusAI 已完成 Step 5/6 产品化收口，具备内部发布/内测基线。**

补充：阶段收口说明见 `docs/archive/FINAL_STATUS_REPORT.md`。

