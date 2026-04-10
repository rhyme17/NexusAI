# PostgreSQL 主切换操作手册（ACA / 停机迁移）

适用策略：**C = 全量停机迁移切换**

该操作手册面向当前 NexusAI 产品化路线中的 Step 5，目标是在维护窗口内，把当前运行态从 `json/sqlite` 切换到 `postgres`，并使用 `migrate_snapshot.py` 完成快照导出与导入。

---

## 1. 前提条件

在切换前确认：

- PostgreSQL 实例可访问
- 已创建目标数据库
- `NEXUSAI_POSTGRES_DSN` 已准备好
- 当前版本已包含：
  - `PostgresStore`
  - `migrate_snapshot.py`
  - `export_runtime_snapshot(...)`
  - `import_runtime_snapshot(...)`
- 后端测试至少通过：
  - `tests/test_migration.py`
  - `tests/test_phase_a_perf.py -k snapshot_migration`

---

## 2. 维护窗口前准备

1. 记录当前配置：
   - `NEXUSAI_STORAGE_BACKEND`
   - `NEXUSAI_SQLITE_PATH`
   - `NEXUSAI_DATA_DIR`
2. 备份当前数据目录或 SQLite 文件。
3. 确认当前服务写入量较低。
4. 通知内部用户进入维护窗口。

---

## 3. 切换步骤

### 0) 非生产预演模式（强烈建议先执行）

在真实维护窗口前，先在本地或 staging 执行一遍完整预演，目标是提前发现快照结构、导入兼容性、校验脚本口径问题。

预演要求：

1. 执行 `export -> verify -> import` 全链路。
2. 记录 `status`、`counts`、`matches`。
3. 保存命令输出到发布门禁文档（建议附时间戳）。

建议预演命令：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python migrate_snapshot.py export --output .\data\cutover-rehearsal.json
python migrate_snapshot.py verify --input .\data\cutover-rehearsal.json
python migrate_snapshot.py import --input .\data\cutover-rehearsal.json
```

若需要对预演耗时加门禁，可执行：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python rehearse_cutover.py --max-total-ms 5000 --max-import-ms 2000
```

也可直接执行候选切换门禁：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python release_gate.py --profile cutover_candidate
```

预演通过标准：

- `verify` 返回 `status=valid`
- `import` 返回 `status=imported`
- `import` 返回 `matches=true`

### 步骤 A：冻结写入

- 暂停前端入口或停止后端进程
- 确保没有新的 `/api/tasks`、`/retry`、`/claim`、`/handoff` 写入继续进入系统
- 如果需要保留服务存活做只读查询，可先开启：

```powershell
$env:NEXUSAI_READ_ONLY_MODE = "true"
```

- 在该模式下，`/api/*` 写入请求会收到 `E_SYSTEM_READ_ONLY`

### 步骤 B：导出运行态快照

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python migrate_snapshot.py export --output .\data\cutover-snapshot.json
```

预期：输出 `status=exported` 与 counts 摘要。

### 步骤 C：切换环境变量

```powershell
$env:NEXUSAI_STORAGE_BACKEND = "postgres"
$env:NEXUSAI_POSTGRES_DSN = "postgresql://user:password@localhost:5432/nexusai"
$env:NEXUSAI_STORAGE_FALLBACK_ON_ERROR = "false"
```

### 步骤 D：导入到 PostgreSQL

建议先校验快照结构：

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python migrate_snapshot.py verify --input .\data\cutover-snapshot.json
```

预期：`status=valid`。

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
python migrate_snapshot.py import --input .\data\cutover-snapshot.json
```

预期：

- `status=imported`
- `matches=true`
- 导入 counts 与 snapshot counts 一致

### 步骤 E：校验

重点校验：

- task 数量
- agent 数量
- 有事件的 task 数量
- 事件总数
- 随机抽查 3 个任务：
  - `task_id`
  - `attempt_history`
  - `consensus`
  - `metadata.decomposition.workflow_run`
  - `metadata.decomposition.dag_nodes`

---

## 4. 建议校验命令

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/tasks -Headers @{"X-API-Key"="your-admin-key"}
Invoke-RestMethod http://localhost:8000/api/agents -Headers @{"X-API-Key"="your-admin-key"}
```

若 debug API 已开启，可进一步对比：

```powershell
Invoke-RestMethod http://localhost:8000/api/debug/storage/export -Headers @{"X-API-Key"="your-admin-key"}
```

---

## 5. 回滚方案

若出现以下任一情况，立即回滚：

- import 失败
- counts 不一致
- 关键任务缺失或 `task_id` 变化
- 关键 workflow metadata 丢失
- 后端启动后核心 API 大面积报错

### 回滚步骤

1. 停止当前 postgres 模式服务
2. 恢复原有环境变量：
   - `NEXUSAI_STORAGE_BACKEND=json` 或 `sqlite`
   - 恢复原 `NEXUSAI_SQLITE_PATH` / `NEXUSAI_DATA_DIR`
3. 使用切换前备份文件恢复原数据
4. 重新启动旧服务并开放写入

---

## 6. 当前状态说明

本 runbook 已与仓库当前能力对齐，但**尚未代表仓库已默认完成 PostgreSQL 主切换**。

也就是说：

- Step 5 工具链已具备基础条件
- 真正切换仍需要在维护窗口内执行并校验
- 切换完成前，仓库仍保持多 backend 兼容状态


