# 🚀 NexusAI 快速开始指南（后端）

这份文档聚焦 `backend/` 目录下的启动与验证方式。当前仓库已经包含可运行的前端 Dashboard，因此后端启动后可以直接与 `../frontend` 联调，而不是只停留在 API 演示阶段。

## 5 分钟快速上手

### 1️⃣ 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2️⃣ 启动后端

```bash
python -m uvicorn app.main:app --reload --port 8000
```

启动后访问：

- API 根地址：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`
- Swagger 文档：`http://localhost:8000/docs`

默认情况下，后端会把任务、Agent 和事件历史以 JSON 形式写入 `backend/data/`，用于本地演示时的轻量持久化。

### 3️⃣ 可选：运行自动演示脚本

```bash
python run_demo.py
```

这会自动启动后端、执行演示请求，并输出一条完整的后端能力演示链路。

### 4️⃣ 可选：联调前端 Dashboard

```bash
cd ..\frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:3000`

---

## 命令参考

### 启动方式

#### 方式 1：手动启动后端（推荐）
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

#### 方式 2：自动启动 + 演示
```bash
cd backend
python run_demo.py
```

#### 方式 3：PowerShell 后台启动后端
```bash
cd backend
powershell -Command "Start-Process python -ArgumentList '-m uvicorn app.main:app --port 8000'"
```

### 运行演示脚本
```bash
cd backend
python demo.py
```

### 调试存储快照（需先开启 debug）
```bash
# 导出当前任务/Agent/事件快照
curl http://localhost:8000/api/debug/storage/export

# 清空任务和事件（保留默认 Agent）
curl -X POST "http://localhost:8000/api/debug/storage/clear?keep_default_agents=true"
```

### 真实 Agent 执行（可选）
```bash
# PowerShell 示例：设置 token
$env:MODELSCOPE_TOKEN="your_token"

# 调用真实执行入口
curl -X POST http://localhost:8000/api/tasks/{task_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent_planner","allow_fallback":true,"arbitration_mode":"judge_on_conflict","judge_agent_id":"agent_reviewer"}'
```

### 运行单元测试
```bash
cd backend

# 快速测试
pytest -q

# 详细输出
pytest -v

# 特定测试
pytest tests/test_api.py -v
pytest tests/test_websocket.py -v
```

---

## 配置

### 环境变量（可选）
复制 `.env.example` 为 `.env`，修改配置：

```bash
Copy-Item .env.example .env
```

可配置项：
- `NEXUSAI_CONSENSUS_STRATEGY_DEFAULT` — 共识策略
- `NEXUSAI_EVENT_HISTORY_MAX` — 事件历史保留条数
- `NEXUSAI_MAX_RETRIES_DEFAULT` — 最大重试次数
- `NEXUSAI_JSON_PERSISTENCE_ENABLED` — 是否启用 JSON 过渡持久化（默认 true）
- `NEXUSAI_DATA_DIR` — JSON 数据目录（默认 `backend/data`）
- `NEXUSAI_SEED_ENABLED` — 是否启用启动时种子加载（默认 false）
- `NEXUSAI_SEED_APPLY_IF_EMPTY` — 仅在存储为空时应用种子（默认 true）
- `NEXUSAI_SEED_FILE` — 种子文件路径（默认 `backend/data/seed.example.json`）
- `NEXUSAI_DEBUG_API_ENABLED` — 是否开放 `/api/debug/storage/*`（默认 false）
- `NEXUSAI_AGENT_EXECUTION_BASE_URL` — 真实执行 Provider 地址（默认 ModelScope）
- `NEXUSAI_AGENT_EXECUTION_MODEL` — 真实执行默认模型
- `NEXUSAI_AGENT_EXECUTION_API_KEY` / `MODELSCOPE_TOKEN` — 真实执行密钥
- `NEXUSAI_AGENT_EXECUTION_TIMEOUT_SECONDS` — 真实执行超时（秒）
- `NEXUSAI_AGENT_EXECUTION_FALLBACK` — 真实执行失败降级策略（simulate/fail）

### 运行参数
```bash
# 修改端口
uvicorn app.main:app --port 9000

# 监听所有 IP（允许远程连接）
uvicorn app.main:app --host 0.0.0.0

# 生产模式（多工作进程）
uvicorn app.main:app --workers 4 --host 0.0.0.0

# 调试模式（详细日志）
uvicorn app.main:app --reload --log-level debug
```

---

## 常见问题

### Q: 后端不启动怎么办？
A: 检查端口 8000 是否被占用。使用 `--port 9000` 改为其他端口。

### Q: ImportError: No module named 'requests'?
A: 运行 `pip install requests` 或 `pip install -r requirements.txt`

### Q: 演示脚本报错？
A: 确保后端已启动。运行 `python run_demo.py` 会自动启动后端。

### Q: 如何添加新 Agent？
A: 
1. 在 `app/agents/` 创建新文件，继承 `BaseAgent`
2. 在 `app/agents/__init__.py` 的 `build_default_agents()` 中注册

### Q: 支持数据库吗？
A: 当前是“内存运行态 + JSON 过渡持久化”。后续可升级为 SQLite / PostgreSQL。

---

## 接下来

✅ **当前后端已可直接配合前端 Dashboard 使用。** 更符合当前仓库状态的下一步是：
- [ ] 补充更稳定的演示脚本与固定 demo 路径
- [ ] 将内存存储替换为 SQLite / PostgreSQL
- [ ] 接入真实 LLM Agent 执行链路

更多信息见：
- 📖 **详细文档**：`IMPLEMENTATION_REPORT.md`
- 🖥️ **前端说明**：`../frontend/README.md`
- 📚 **API 文档**：http://localhost:8000/docs（启动后）
- 🎬 **演示脚本**：`demo.py`

---

## 架构概览

```
Next.js Dashboard
   ↓
API Gateway (FastAPI)
   ↓
┌─────────────────────────────────────┐
│  Workflow Engine (任务拆解)          │
│  Task Router (智能分发)              │
│  Consensus Engine (仲裁)             │
│  Message Bus (事件总线)              │
└─────────────────────────────────────┘
   ↓
5 个预定义 Agent (可扩展)
```

---

**状态**：✅ 后端 MVP 已完成并已接入前端 Dashboard  
**版本**：v0.1.0  
**最后更新**：2026-04-06

