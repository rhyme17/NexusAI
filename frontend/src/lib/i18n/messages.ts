export type Locale = "zh-CN" | "en";

export interface I18nMessages {
  dashboardTitle: string;
  dashboardSubtitle: string;
  backendErrorPrefix: string;
  agentErrorPrefix: string;
  sectionSystemOverview: string;
  sectionTasks: string;
  sectionCreateTask: string;
  sectionTaskDetail: string;
  sectionEventStream: string;
  sectionEventInsights: string;
  sectionTaskFlow: string;
  sectionAgentGraph: string;
  healthOnline: string;
  healthOffline: string;
  healthChecking: string;
  refreshAll: string;
  refreshing: string;
  languageToggleLabel: string;
  executionSectionTitle: string;
  executionSectionHint: string;
  executionModeLabel: string;
  executionErrorPolicyLabel: string;
  executionAgentsLabel: string;
  executionAllowFallbackLabel: string;
  executionFallbackModeLabel: string;
  executionArbitrationLabel: string;
  executionJudgeAgentLabel: string;
  executionPreviewButton: string;
  executionPreviewingButton: string;
  executionRunButton: string;
  executionRunningButton: string;
  executionPreviewTitle: string;
  executionPreviewEmpty: string;
  executionPreviewStale: string;
  executionPreviewSummary: string;
  executionPreviewSteps: string;
  executionPreviewEvents: string;
  executionPreviewWarnings: string;
  executionNoWarnings: string;
  executionStrictPreviewFirst: string;
  executionPreviewFailed: string;
  executionRunFailed: string;
  executionPipelinePlaceholder: string;
  executionModeSingle: string;
  executionModePipeline: string;
  executionModeParallel: string;
  executionApiKeyLabel: string;
  executionApiKeyPlaceholder: string;
  executionQuickActionsTitle: string;
  executionOwnershipTitle: string;
  executionAdvancedTitle: string;
  explanationSectionTitle: string;
  routingExplanationTitle: string;
  consensusExplanationTitle: string;
  arbitrationExplanationTitle: string;
  explanationEmpty: string;
}

export const messages: Record<Locale, I18nMessages> = {
  "zh-CN": {
    dashboardTitle: "NexusAI 协作中枢",
    dashboardSubtitle: "多智能体任务协作与执行全景",
    backendErrorPrefix: "后端错误",
    agentErrorPrefix: "Agent 错误",
    sectionSystemOverview: "系统总览",
    sectionTasks: "任务列表",
    sectionCreateTask: "创建任务",
    sectionTaskDetail: "任务详情",
    sectionEventStream: "事件流",
    sectionEventInsights: "事件洞察",
    sectionTaskFlow: "任务流程图",
    sectionAgentGraph: "智能体关系图",
    healthOnline: "在线",
    healthOffline: "离线",
    healthChecking: "检测中",
    refreshAll: "刷新全部数据",
    refreshing: "刷新中...",
    languageToggleLabel: "语言",
    executionSectionTitle: "执行编排",
    executionSectionHint: "建议先确认执行模式、智能体路径与回退策略，再开始执行，更稳定也更易排查。",
    executionModeLabel: "执行模式",
    executionErrorPolicyLabel: "出错处理策略",
    executionAgentsLabel: "串行 / 并行智能体 ID（逗号分隔，可点选下方标签）",
    executionAllowFallbackLabel: "执行失败时允许回退",
    executionFallbackModeLabel: "回退模式",
    executionArbitrationLabel: "仲裁模式",
    executionJudgeAgentLabel: "裁决智能体（Judge Agent）",
    executionPreviewButton: "预览执行计划",
    executionPreviewingButton: "预览中...",
    executionRunButton: "开始执行",
    executionRunningButton: "执行中...",
    executionPreviewTitle: "执行预览",
    executionPreviewEmpty: "建议先预览一次，确认步骤、事件和告警后再执行。",
    executionPreviewStale: "你的配置已变化，当前预览可能已过时，请重新预览后再执行。",
    executionPreviewSummary: "预览概览",
    executionPreviewSteps: "步骤",
    executionPreviewEvents: "预估事件",
    executionPreviewWarnings: "预览告警",
    executionNoWarnings: "无告警",
    executionStrictPreviewFirst: "请先生成最新预览，再执行当前配置。",
    executionPreviewFailed: "预览执行失败。",
    executionRunFailed: "执行失败。",
    executionPipelinePlaceholder: "例如：agent_planner,agent_research,agent_writer",
    executionModeSingle: "单智能体",
    executionModePipeline: "串行 Pipeline",
    executionModeParallel: "并行 Batch",
    executionApiKeyLabel: "模型 API Key（可选，填写后优先使用你的 Key）",
    executionApiKeyPlaceholder: "sk-... 或你的 OpenAI-compatible Key",
    executionQuickActionsTitle: "快速操作",
    executionOwnershipTitle: "任务所有权",
    executionAdvancedTitle: "高级执行配置",
    explanationSectionTitle: "协作解释",
    routingExplanationTitle: "路由解释",
    consensusExplanationTitle: "共识解释",
    arbitrationExplanationTitle: "仲裁解释",
    explanationEmpty: "当前暂无可解释信息。"
  },
  en: {
    dashboardTitle: "NexusAI Orchestration Hub",
    dashboardSubtitle: "Overview for multi-agent task collaboration and execution",
    backendErrorPrefix: "Backend Error",
    agentErrorPrefix: "Agent Error",
    sectionSystemOverview: "System Overview",
    sectionTasks: "Tasks",
    sectionCreateTask: "Create Task",
    sectionTaskDetail: "Task Detail",
    sectionEventStream: "Event Stream",
    sectionEventInsights: "Event Insights",
    sectionTaskFlow: "Task Flow",
    sectionAgentGraph: "Agent Graph",
    healthOnline: "online",
    healthOffline: "offline",
    healthChecking: "checking",
    refreshAll: "Refresh All",
    refreshing: "Refreshing...",
    languageToggleLabel: "Language",
    executionSectionTitle: "Execution Orchestration",
    executionSectionHint: "Confirm mode, agent path, and fallback behavior before running so execution stays understandable and safe.",
    executionModeLabel: "Execution Mode",
    executionErrorPolicyLabel: "Error Policy",
    executionAgentsLabel: "Pipeline / Parallel Agent IDs (comma-separated)",
    executionAllowFallbackLabel: "Allow fallback",
    executionFallbackModeLabel: "Fallback Mode",
    executionArbitrationLabel: "Arbitration",
    executionJudgeAgentLabel: "Judge Agent",
    executionPreviewButton: "Preview Execution",
    executionPreviewingButton: "Previewing...",
    executionRunButton: "Execute",
    executionRunningButton: "Executing...",
    executionPreviewTitle: "Execution Preview",
    executionPreviewEmpty: "Preview first to confirm steps, expected events, and warnings before execution.",
    executionPreviewStale: "Configuration changed after the last preview. Refresh the preview before executing.",
    executionPreviewSummary: "Preview Summary",
    executionPreviewSteps: "Steps",
    executionPreviewEvents: "Estimated Events",
    executionPreviewWarnings: "Preview Warnings",
    executionNoWarnings: "none",
    executionStrictPreviewFirst: "Generate an up-to-date preview before executing this configuration.",
    executionPreviewFailed: "Failed to preview execution.",
    executionRunFailed: "Execution failed.",
    executionPipelinePlaceholder: "agent_planner,agent_research,agent_writer",
    executionModeSingle: "Single Agent",
    executionModePipeline: "Serial Pipeline",
    executionModeParallel: "Parallel Batch",
    executionApiKeyLabel: "Model API Key (optional, takes priority over server key)",
    executionApiKeyPlaceholder: "sk-... or your OpenAI-compatible key",
    executionQuickActionsTitle: "Quick Actions",
    executionOwnershipTitle: "Ownership",
    executionAdvancedTitle: "Advanced Execution",
    explanationSectionTitle: "Collaboration Explanations",
    routingExplanationTitle: "Routing Explanation",
    consensusExplanationTitle: "Consensus Explanation",
    arbitrationExplanationTitle: "Arbitration Explanation",
    explanationEmpty: "No explanation data is available yet."
  }
};

