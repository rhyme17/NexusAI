# NexusAI 优化准备清单

本清单用于在执行优化工作前建立变更前基线。

## 1）依赖与版本

### 后端（`backend/requirements.txt`）
- `fastapi==0.116.0`
- `uvicorn[standard]==0.35.0`
- `pydantic==2.11.7`
- `pytest==8.3.3`
- `httpx==0.28.1`
- `requests==2.31.0`
- `openai==1.51.2`

### 前端（`frontend/package.json`）
- `next@14.2.5`
- `react@18.3.1`
- `react-dom@18.3.1`
- `reactflow@11.11.4`
- `typescript@5.6.2`
- `vitest@^4.1.2`
- `@playwright/test@^1.54.2`

## 2）推荐环境准备

### 后端环境（从 `.env.example` 复制到 `backend/.env`）
目的：保证执行、重试和持久化行为可复现。

步骤：
1. 将 `.env.example` 复制为 `.env`。
2. 设置/确认：
   - `NEXUSAI_STORAGE_BACKEND=json` (or `sqlite` for the new transitional backend)
   - `NEXUSAI_JSON_PERSISTENCE_ENABLED=true`
   - `NEXUSAI_SQLITE_PATH=backend/data/nexusai.db` (when `NEXUSAI_STORAGE_BACKEND=sqlite`)
   - `NEXUSAI_EVENT_HISTORY_MAX=2000`
   - `NEXUSAI_MAX_RETRIES_DEFAULT=2`
3. 如果需要真实执行，请提供以下任一变量：
   - `NEXUSAI_AGENT_EXECUTION_API_KEY`
   - `MODELSCOPE_TOKEN`

### 前端环境（从 `.env.local.example` 复制到 `frontend/.env.local`）
目的：确保开发/测试时 API 与 WebSocket 路径解析正确。

步骤：
1. 将 `.env.local.example` 复制为 `.env.local`。
2. 设置/确认：
   - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
   - `NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000`

## 3）工具链与校验门禁

目的：在每个优化步骤前后尽早失败、尽早发现问题。

### 后端
1. 安装依赖。
2. 运行：
   - `pytest -q`

### 前端
1. 安装依赖。
2. 运行：
   - `npm run typecheck`
   - `npm run test`
   - `npm run e2e` (with backend running)

## 4）可选加固工具（下一轮）

目的：提升静态质量与性能可见性。

- 后端：
  - `ruff`：用于 lint/format
  - `mypy`：用于类型检查
  - `pytest-benchmark`：用于热点路径回归检查
- 前端：
  - `@next/bundle-analyzer`：用于观察包体积

## 5）变更执行协议

目的：避免回归并保持核心用户链路稳定。

1. 先跑基线测试并记录当前通过状态。
2. 每次只执行一个优化主题。
3. 对修改到的模块运行定向测试。
4. 回归后端/前端完整测试集。
5. 继续通过 E2E 验证用户可见行为：
   - 创建 + 成功
   - 失败 + 重试 + 成功
   - 重试耗尽
   - 预览 + 执行

