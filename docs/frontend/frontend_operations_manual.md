# NexusAI 前端用户使用手册（内部完整版）

更新日期：2026-04-08
适用对象：研发、测试、运维值守

## 1. 文档目的与适用范围

本手册用于指导内部用户在当前前端版本完成以下闭环：

- 配置访问与执行密钥
- 创建任务并进入单任务工作区
- 执行真实任务（非模拟）
- 观察协作事件与流程状态
- 处理失败与重试
- 进行受控数据重置（需权限）

相关页面：
- `/`
- `/tasks`
- `/tasks/{taskId}`
- `/agents`
- `/settings`

## 2. 前置条件

### 2.1 运行环境

- Node.js 18+
- 浏览器可访问前端与后端
- 后端服务已启动且可用

### 2.2 关键配置

- 用户 AI Key（前端侧保存）：`MODELSCOPE_ACCESS_TOKEN`
- 后端 API Key（如启用鉴权）：`X-API-Key`

建议先确认后端可访问：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## 3. 信息架构与职责边界

- `总览 /`：做全局判断（健康、焦点任务、入口导航）
- `任务台 /tasks`：做任务创建、筛选与进入详情
- `单任务 /tasks/{taskId}`：做执行、观测、排障和结果核验
- `智能体 /agents`：做智能体视角分析与状态管理
- `设置 /settings`：做语言、密钥、Agent 注册与运维控制

## 4. 设置页使用说明

位置：`/settings`

### 4.1 语言设置

- 入口：`设置 /settings`
- 作用：切换中文/英文界面语言

### 4.6 连接测试与高风险操作确认

- 可在 `设置 /settings` 执行后端连接测试
- 服务器数据操作需要二次确认（确认弹窗 + 口令）
- 执行前会显示审计 ID 提示，便于排查

### 4.2 用户 AI Key

- 入口：`设置 /settings > 用户 AI Key`
- 作用：执行请求自动携带用户 key，用于真实模型调用
- 存储：浏览器本地（仅当前浏览器环境）

### 4.3 后端 API Key

- 入口：`设置 /settings > 后端 API Key`
- 作用：自动附加到受保护的后端接口请求
- 适用：后端启用了 API Key 鉴权时

### 4.4 Agent 注册（技能可选择）

- 入口：`设置 /settings > 注册 Agent`
- 方式：先选技能标签（多选），再按需补充自定义技能

### 4.5 服务器数据控制（需后端 debug + admin）

- Clear events
- Clear tasks+events
- Reset + restore default agents

用于联调清场，非发布态常规操作。

## 5. 标准业务流程（真实执行）

### 步骤 1：创建任务

进入 `/tasks`，在创建面板输入：
- objective（至少 3 个字符）
- priority（low/medium/high）

提交后自动跳转 `/tasks/{taskId}`。

### 步骤 2：执行前检查

在任务详情页 `执行` 页签确认：
- 顶部提示显示已检测到用户 AI Key
- 执行模式与 agent 列表符合预期
- 默认 `allow fallback` 关闭（建议保持）

### 步骤 3：预览执行

点击 `预览执行`，核对：
- 预计步骤数量
- 预计事件列表
- 预览告警（warnings）

### 步骤 4：开始执行

点击 `开始执行`。

执行后关注：
- 任务状态是否推进到 `in_progress` / `completed`
- 结果对象中是否出现 `mode=real`
- 事件流中是否出现 `AgentExecutionStart/Result`

### 步骤 5：结果核验

在 `概览` 页签检查：
- `结果` 面板内容
- `执行提示` 是否有错误或可重试提示
- `routing/consensus/arbitration` 可解释信息
- 如需对外提交，可在结果区导出 `.md/.txt` 文件或复制 Markdown

## 6. 执行模式说明

### 6.1 single

- 单 agent 直接执行
- 适合快速验证链路

### 6.2 pipeline

- 按 agent 序列串行执行
- 适合研究-分析-写作型任务

### 6.3 parallel

- 多 agent 并行执行后择优
- 适合探索多个候选方案

## 7. 真实执行与模拟执行边界

### 真实执行

- 通过 `预览执行` + `开始执行`
- 需要有效 AI Key 与可用模型服务
- 结果通常包含 `mode=real` 与 execution metrics

### 模拟执行

- 通过 `Simulate Success/Failure` 触发
- 用于联调/回归，不代表真实模型调用

### fallback 策略

- 当前默认关闭 fallback
- 仅在手动启用后，真实执行失败才可能回退到模拟

## 8. 事件与可观测性

单任务页可查看：

- 事件洞察卡（最新 owner、handoff 数、最新决策、最近失败）
- 事件流（支持类型筛选、时间范围过滤）
- DAG 流程图与运行态（ready/running/blocked/completed/failed）

建议排障顺序：
1. 看执行提示
2. 看事件流错误事件
3. 看流程运行态是否阻塞
4. 决定是否重试

## 9. 智能体页面操作指南

在 `/agents` 可进行：

- 技能筛选与状态筛选
- 中文关键词检索（例如：规划、研究、写作、评审、仲裁）
- 在线状态变更（online/offline/busy）
- 角色分布查看（列表/雷达图）

适用于：
- 观察协作网络
- 排查“找不到合适 agent”类问题
- 调整值守状态

## 10. 常见故障与处理

### 10.1 无法发起执行

检查：
- 后端在线状态
- 用户 AI Key 是否设置
- 后端 API Key 是否有效（若启用鉴权）
- 是否先做了执行预览

### 10.2 执行失败（非模拟）

建议：
- 保持 fallback 关闭，先获取真实错误
- 看错误码与 `retryable` 提示
- 修复配置后再 retry

### 10.3 输出与任务目标关联度不高

优化方式：
- 将 objective 写成结构化要求
- 使用 pipeline，包含 writer/reviewer
- 在目标中明确输出格式（Markdown、章节、结论与行动）

## 11. 推荐任务模板

```text
请调研“区块链在信息安全中的应用”，并输出 Markdown 报告：
- 背景与问题定义
- 典型应用场景（至少 3 个）
- 技术优缺点与风险
- 案例与证据（来源类型说明）
- 结论与可执行建议（按优先级）
```

## 12. 版本与限制

当前前端版本能力以 `frontend/README.md` 为准，已支持：

- 任务创建与单任务工作区
- 执行预览与真实执行触发
- 协作事件流与可解释性展示
- 智能体管理基础能力

已知限制：
- 更细粒度会话/权限体验仍在迭代
- 本地演示与内部发布配置存在差异，请遵循发布基线文档

---

配套文档：
- `docs/frontend/frontend_quick_guide.md`
- `frontend/README.md`
- `docs/release_baseline.md`
- `RELEASE_GATE_CHECKLIST.md`

