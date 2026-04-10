# NexusAI 文档语言规范

更新日期：2026-04-07

本文档用于统一仓库内 Markdown 文档的默认语言与书写规则，支撑 Step 6 的发布封板与文档收口。

---

## 1. 默认语言

仓库内自有 Markdown 文档默认采用：

- **中文为主**
- 首次出现的重要技术名词可采用“中文 + 英文/原词”并列
- 第二次出现后可直接使用中文或保留约定俗成的技术词

示例：

- 智能体（Agent）
- 共识（Consensus）
- 仲裁（Arbitration）
- 工作流运行态（workflow runtime）

---

## 2. 必须保留原样的内容

以下内容**不得翻译**，以避免影响运行、复制或验证：

- 环境变量名，如 `NEXUSAI_STORAGE_BACKEND`
- API 路径，如 `POST /api/tasks/{task_id}/retry`
- 代码块中的命令、JSON key、YAML key、Python/TypeScript 标识符
- 文件路径、目录名、类名、函数名、测试名
- 状态值与协议值，如 `queued`、`failed`、`majority_vote`、`judge_on_conflict`

---

## 3. 推荐翻译策略

### 3.1 标题与正文

- Markdown 标题统一使用中文
- 正文说明、步骤说明、影响说明、结论说明统一使用中文
- 代码块前后的解释文字优先用中文表达

### 3.2 技术术语

建议保留以下常见写法：

- API
- WebSocket
- Dashboard
- MVP
- E2E
- debug
- fallback
- claim / handoff
- seed
- runbook
- cutover

说明：这些词在仓库已有上下文中已形成稳定含义，可保留英文原词，以减少歧义。

### 3.3 示例数据

- 请求体/响应体中的业务说明文字可中文化
- 结构字段名保持原样
- 若示例字符串本身影响测试或复制执行，应保持原样

---

## 4. 文档范围

本规范适用于仓库中的自有 Markdown 文档，包括但不限于：

- 根目录产品与状态文档
- `backend/` 运行、迁移、实现文档
- `frontend/` 使用与测试文档
- `docs/` 架构、协议、API、发布基线文档
- `references/` 下的设计与组件参考文档

不包含：

- `.venv/`、`node_modules/`、`.pytest_cache/` 等第三方或工具生成目录中的 Markdown
- 第三方许可证文本

---

## 5. 变更要求

后续若新增或修改 Markdown 文档，应满足：

1. 标题与正文优先使用中文
2. 命令、配置项、路径、代码块保持可复制
3. 与 `README.md`、`docs/release_baseline.md`、`RELEASE_GATE_CHECKLIST.md` 的口径保持一致
4. 若引用 Step 5 / Step 6 状态，应避免与当前发布结论冲突

---

## 6. 当前执行说明

截至 2026-04-07：

- 仓库主入口文档已按中文优先方向统一
- 发布、迁移、API、前后端 README 已进入中文口径
- `references/` 下的大体量设计参考文档仍可继续按本规范分批收口

这意味着仓库已经具备“中文优先”的文档治理基线，后续只需按批次继续完成余下参考资料的中文化。

