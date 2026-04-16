# NexusAI

<div align="center">

[![许可证: MIT](https://img.shields.io/badge/许可证-MIT-yellow.svg)](https://opensource.org/licenses/MIT)[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green.svg)](https://fastapi.tiangolo.com/)[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

**AI 智能体协作网络的编排中枢**

让多个 AI Agent 像团队一样通信、协作、决策与执行。

</div>

## 主要功能

- 用户登录、角色鉴权（管理员/普通用户）
- 任务创建、执行、重试、结果查询
- 智能体注册与管理
- 任务事件流、流程图、WebSocket 实时更新
- 执行配置（单智能体、流水线、并行）
- 可选的调试清理接口与种子恢复

## 项目结构

```text
NexusAI/
├── backend/                                # 后端服务（FastAPI）
│   ├── app/
│   │   ├── agents/                         # 智能体角色实现（planner/research/analyst/...）
│   │   ├── api/                            # REST/WS 接口层（tasks/agents/auth/events/debug）
│   │   ├── core/                           # 配置、安全、启动、错误协议等核心模块
│   │   ├── middleware/                     # 中间件（审计日志等）
│   │   ├── models/                         # Pydantic 数据模型（task/agent/message/auth）
│   │   ├── services/                       # 业务服务层（workflow/router/store/execution/bus）
│   │   └── main.py                         # FastAPI 入口
│   ├── data/                               # 本地持久化与演练/门禁证据文件
│   │   ├── migration-smoke/                # 迁移冒烟样本
│   │   └── release-gate-history/           # release gate 历史归档
│   ├── tests/                              # 后端测试（API/协议/性能/迁移/WS 等）
│   ├── migrate_snapshot.py                 # 快照导出/校验/导入工具
│   ├── rehearse_cutover.py                 # 切库预演脚本
│   ├── release_gate.py                     # 发布门禁脚本
│   ├── requirements.txt                    # 后端依赖
│   └── README.md                           # 后端说明
├── docs/                                   # 文档主目录
│   ├── api_spec.md                         # API 说明
│   ├── architecture.md                     # 架构说明
│   ├── protocol.md                         # 协议说明（任务/事件/错误）
│   ├── user_manual.md                      # 用户手册
│   ├── developer_manual.md                 # 开发与运维手册
│   ├── release_baseline.md                 # 发布基线说明
│   ├── hackathon_report_and_agent_protocol.md  # 黑客松汇报大纲 + agents 通信协议摘要
│   └── archive/                            # 历史阶段文档归档
├── frontend/                               # 前端应用（Next.js）
│   ├── src/
│   │   ├── app/                            # App Router 页面
│   │   ├── components/                     # UI 组件（任务页、事件流、流程图等）
│   │   ├── hooks/                          # 前端业务 hooks
│   │   ├── lib/                            # API 客户端、i18n、ws、上下文与工具
│   │   └── middleware.ts                   # 前端中间件（路由与访问控制）
│   ├── tests/e2e/                          # Playwright 端到端测试
│   ├── package.json                        # 前端依赖与脚本
│   └── README.md                           # 前端说明
├── prospectus.md                           # 产品计划书
├── RELEASE_GATE_CHECKLIST.md               # 发布门禁清单（保留在根目录）
├── main.py                                 # 本地入口/调试脚本
├── test_main.http                          # HTTP 请求调试集合
└── README.md                               # 项目总览
```

## 快速开始（本地）

### 1) 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 3) 访问地址

- 前端：`http://localhost:3000`
- 后端健康检查：`http://localhost:8000/health`
- 后端 API 文档：`http://localhost:8000/docs`

## Ubuntu 服务器部署

完整部署、更新、排障命令见：

- `docs/developer_manual.md`

用户侧操作说明见：

- `docs/user_manual.md`

## 基础验证命令

```bash
# backend
cd backend
pytest -q

# frontend
cd frontend
npm run build
```

## 已知注意项

- 默认存储后端为 SQLite（`NEXUSAI_STORAGE_BACKEND=sqlite`）；如需切换 PostgreSQL，请参考 `docs/developer_manual.md` 与 `backend/POSTGRES_CUTOVER_RUNBOOK.md`。
- `frontend/package.json` 当前固定 `next@14.2.5`，有安全升级提示，建议后续升级到官方修复版本。
- 真实模型执行依赖有效的用户 API Key 与可访问的模型服务地址。
- 服务器生产模式下，前端必须先执行 `npm run build`，再 `npm run start`。

## 相关文档

- 产品计划书：`prospectus.md`
- 架构：`docs/architecture.md`
- 协议：`docs/protocol.md`
- API 说明：`docs/api_spec.md`
- 黑客松汇报与协议速览：`docs/hackathon_report_and_agent_protocol.md`
- 用户手册：`docs/user_manual.md`
- 开发与运维手册：`docs/developer_manual.md`

## 许可证

MIT
