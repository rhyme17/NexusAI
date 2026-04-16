import { useEffect, useMemo, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";
import { useCurrentUser } from "@/hooks/use-current-user";
import { getAgentDisplayName } from "@/lib/agents/display-name";
import {
  Agent,
  ArbitrationMode,
  ExecutionMode,
  FallbackMode,
  PipelineErrorPolicy,
  Task,
  TaskAttemptsResponse,
  TaskConsensusResponse,
  TaskExecutionPreviewResponse,
} from "@/lib/api/types";
import {
  buildConsensusComparisonRows,
  buildTaskResultExportContent,
  formatTimestamp,
  getArbitrationExplanation,
  getConsensusExplanation,
  getRoutingExplanation,
  getRetryErrorMessage,
  getTaskDecomposition,
  getTaskResultErrorSummary,
  getUserFacingResultContent,
  toPrettyJson
} from "./task-detail-helpers";

interface TaskDetailProps {
  task: Task | null;
  onTaskPatched: (task: Task) => void;
  agents: Agent[];
  userApiKey?: string;
}

type TaskDetailTab = "overview" | "execution" | "coordination";

export function TaskDetail({ task, onTaskPatched, agents, userApiKey }: TaskDetailProps) {
  const { isChinese, text } = useI18n();
  const { user: currentUser } = useCurrentUser();
  const isAdminUser = currentUser?.role === "admin";
  const hasUserApiKey = Boolean(userApiKey?.trim());
  const [attempts, setAttempts] = useState<TaskAttemptsResponse | null>(null);
  const [consensus, setConsensus] = useState<TaskConsensusResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<
    "simulate-success" | "simulate-failure" | "retry" | "claim" | "handoff" | "preview" | "execute" | null
  >(null);
  const [claimAgentId, setClaimAgentId] = useState("");
  const [handoffToAgentId, setHandoffToAgentId] = useState("");
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("single");
  const [pipelineAgentIdsText, setPipelineAgentIdsText] = useState("");
  const [pipelineErrorPolicy, setPipelineErrorPolicy] = useState<PipelineErrorPolicy>("fail_fast");
  const [allowFallback, setAllowFallback] = useState(true);
  const [fallbackMode, setFallbackMode] = useState<FallbackMode>("simulate");
  const [arbitrationMode, setArbitrationMode] = useState<ArbitrationMode>("off");
  const [judgeAgentId, setJudgeAgentId] = useState("agent_judge");
  const [executionPreview, setExecutionPreview] = useState<TaskExecutionPreviewResponse | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TaskDetailTab>("overview");
  const [resultActionMessage, setResultActionMessage] = useState<string | null>(null);
  const [pipelineAgentIdsDirty, setPipelineAgentIdsDirty] = useState(false);

  const decomposition = getTaskDecomposition(task);
  const consensusRows = buildConsensusComparisonRows(consensus);
  const routingExplanation = getRoutingExplanation(task);
  const consensusExplanation = getConsensusExplanation(consensus);
  const arbitrationExplanation = getArbitrationExplanation(task);

  const agentById = useMemo(() => {
    const map = new Map<string, Agent>();
    agents.forEach((agent) => map.set(agent.agent_id, agent));
    return map;
  }, [agents]);

  function getAgentLabelById(agentId: string): string {
    if (!isChinese) {
      return agentId;
    }
    const agent = agentById.get(agentId);
    if (!agent) {
      return agentId;
    }
    return getAgentDisplayName(agent, true);
  }

  function formatAgentList(agentIds: string[]): string {
    if (!agentIds.length) {
      return isChinese ? "无" : "none";
    }
    return agentIds.map((agentId) => getAgentLabelById(agentId)).join(", ");
  }

  function localizeCollaborationText(raw: string): string {
    if (!isChinese) {
      return raw;
    }
    const normalized = raw.trim();
    if (!normalized) {
      return raw;
    }
    if (normalized === "Selected by skill overlap and status.") {
      return "根据技能匹配度与当前状态完成选择。";
    }
    const noOverlapMatch = normalized.match(
      /^No direct skill overlap found; selected \[(.+)] using agent availability and low active task count\.?$/i
    );
    if (noOverlapMatch) {
      const selectedIds = noOverlapMatch[1]
        .split(",")
        .map((item) => item.trim().replace(/^['\"]|['\"]$/g, ""))
        .filter(Boolean)
        .map((item) => getAgentLabelById(item));
      return `未发现直接技能匹配；系统基于智能体可用性与较低活跃任务数，选择了 [${selectedIds.join(", ")}]。`;
    }
    return normalized
      .replace(/proposal_count=/gi, "方案数=")
      .replace(/highest confidence/gi, "最高置信度")
      .replace(/judge override applied/gi, "已应用裁决覆盖");
  }

  const recommendedPipelineAgentIds = useMemo(() => {
    if (!task) {
      return [] as string[];
    }

    const unique = new Set<string>();
    const seededIds = isAdminUser ? task.assigned_agent_ids : [...task.assigned_agent_ids, ...agents.map((agent) => agent.agent_id)];
    seededIds.forEach((agentId) => {
      const normalized = agentId.trim();
      if (normalized) {
        unique.add(normalized);
      }
    });

    const fallbackTarget = isAdminUser ? 1 : 3;
    if (unique.size === 0) {
      agents.slice(0, fallbackTarget).forEach((agent) => unique.add(agent.agent_id));
    }
    return Array.from(unique).slice(0, isAdminUser ? Math.max(1, unique.size) : 3);
  }, [agents, isAdminUser, task]);

  const pipelineAgentIds = useMemo(() => parsePipelineAgentIds(pipelineAgentIdsText), [pipelineAgentIdsText]);
  const pipelineAgentIdSet = useMemo(() => new Set(pipelineAgentIds), [pipelineAgentIds]);

  useEffect(() => {
    if (!task) {
      setAttempts(null);
      setConsensus(null);
      return;
    }

    void apiClient
      .getTaskAttempts(task.task_id)
      .then(setAttempts)
      .catch(() => setAttempts(null));

    void apiClient
      .getTaskConsensus(task.task_id)
      .then(setConsensus)
      .catch(() => setConsensus(null));

    setClaimAgentId(task.current_agent_id ?? task.assigned_agent_ids[0] ?? "");
    setHandoffToAgentId(task.assigned_agent_ids.find((id) => id !== task.current_agent_id) ?? "");
    setExecutionMode("single");
    setPipelineAgentIdsDirty(false);
    setPipelineErrorPolicy("fail_fast");
    setAllowFallback(false);
    setFallbackMode("fail");
    setArbitrationMode("off");
    setJudgeAgentId("agent_judge");
    setExecutionPreview(null);
    setExecutionError(null);
    setActiveTab(task.status === "completed" ? "overview" : "execution");
  }, [task]);

  useEffect(() => {
    if (!task) {
      return;
    }
    if (pipelineAgentIdsDirty) {
      return;
    }
    const nextIds = recommendedPipelineAgentIds.join(",");
    setPipelineAgentIdsText(nextIds);
  }, [pipelineAgentIdsDirty, recommendedPipelineAgentIds, task]);

  function parsePipelineAgentIds(raw: string): string[] {
    const unique = new Set<string>();
    raw
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .forEach((item) => unique.add(item));
    return Array.from(unique);
  }

  function setPipelineAgentIds(nextIds: string[]) {
    setPipelineAgentIdsText(Array.from(new Set(nextIds.map((item) => item.trim()).filter(Boolean))).join(","));
    setPipelineAgentIdsDirty(true);
  }

  function togglePipelineAgent(agentId: string) {
    const current = parsePipelineAgentIds(pipelineAgentIdsText);
    if (current.includes(agentId)) {
      setPipelineAgentIds(current.filter((item) => item !== agentId));
      return;
    }
    setPipelineAgentIds([...current, agentId]);
  }

  function selectRecommendedPipelineAgents() {
    setPipelineAgentIdsText(recommendedPipelineAgentIds.join(","));
    setPipelineAgentIdsDirty(false);
  }

  function buildExecutionPayload() {
    const pipelineAgentIds = parsePipelineAgentIds(pipelineAgentIdsText);
    return {
      agent_id: claimAgentId || task?.current_agent_id || undefined,
      execution_mode: executionMode,
      api_key: userApiKey?.trim() ? userApiKey.trim() : undefined,
      pipeline_agent_ids: pipelineAgentIds,
      pipeline_error_policy: pipelineErrorPolicy,
      allow_fallback: allowFallback,
      fallback_mode: fallbackMode,
      arbitration_mode: arbitrationMode,
      judge_agent_id: judgeAgentId || undefined
    };
  }

  function normalizeExecutionConfig(config: {
    agent_id?: string;
    execution_mode?: ExecutionMode;
    api_key?: string;
    pipeline_agent_ids?: string[];
    pipeline_error_policy?: PipelineErrorPolicy;
    allow_fallback?: boolean;
    fallback_mode?: FallbackMode;
    arbitration_mode?: ArbitrationMode;
    judge_agent_id?: string;
  }) {
    const mode = config.execution_mode ?? "single";
    return {
      agent_id: config.agent_id,
      execution_mode: mode,
      api_key: config.api_key,
      pipeline_agent_ids: mode === "single" ? [] : (config.pipeline_agent_ids ?? []),
      pipeline_error_policy: config.pipeline_error_policy ?? "fail_fast",
      allow_fallback: config.allow_fallback ?? true,
      fallback_mode: config.fallback_mode ?? "simulate",
      arbitration_mode: config.arbitration_mode ?? "off",
      judge_agent_id: config.judge_agent_id
    };
  }

  const executionPayloadSignature = JSON.stringify(normalizeExecutionConfig(buildExecutionPayload()));
  const previewSignature = executionPreview
    ? JSON.stringify(
        normalizeExecutionConfig({
          agent_id: executionPreview.steps[0]?.agent_id ?? claimAgentId ?? task?.current_agent_id ?? undefined,
          execution_mode: executionPreview.execution_mode,
          api_key: userApiKey?.trim() ? userApiKey.trim() : undefined,
          pipeline_agent_ids: executionPreview.steps.map((step) => step.agent_id),
          pipeline_error_policy: executionPreview.pipeline_error_policy,
          allow_fallback: executionPreview.allow_fallback,
          fallback_mode: executionPreview.fallback_mode,
          arbitration_mode: executionPreview.arbitration_mode,
          judge_agent_id: executionPreview.judge_agent_id || undefined
        })
      )
    : null;
  const isPreviewStale = executionPreview !== null && previewSignature !== executionPayloadSignature;
  const showOverview = activeTab === "overview";
  const showExecution = activeTab === "execution";
  const showCoordination = activeTab === "coordination";

  async function runExecutionPreview() {
    if (!task) {
      return;
    }
    setBusyAction("preview");
    setExecutionError(null);
    try {
      const preview = await apiClient.previewExecuteTask(task.task_id, buildExecutionPayload());
      setExecutionPreview(preview);
    } catch (err) {
      setExecutionPreview(null);
      setExecutionError(
        getUserFacingErrorMessage(err, {
          isChinese,
          context: "execution_preview",
          fallback: text.executionPreviewFailed
        })
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function runExecuteTask() {
    if (!task) {
      return;
    }
    if (!executionPreview || isPreviewStale) {
      setExecutionError(text.executionStrictPreviewFirst);
      return;
    }
    setBusyAction("execute");
    setExecutionError(null);
    try {
      const updated = await apiClient.executeTask(task.task_id, buildExecutionPayload());
      onTaskPatched(updated);
      await reloadArtifacts(task.task_id);
    } catch (err) {
      setExecutionError(
        getUserFacingErrorMessage(err, {
          isChinese,
          context: "execution_run",
          fallback: text.executionRunFailed
        })
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function reloadArtifacts(taskId: string) {
    const [nextAttempts, nextConsensus] = await Promise.all([
      apiClient.getTaskAttempts(taskId).catch(() => null),
      apiClient.getTaskConsensus(taskId).catch(() => null)
    ]);
    setAttempts(nextAttempts);
    setConsensus(nextConsensus);
  }

  async function runAction(action: "simulate-success" | "simulate-failure" | "retry") {
    if (!task) {
      return;
    }

    setBusyAction(action);
    setActionError(null);

    try {
      if (action === "simulate-success") {
        const updated = await apiClient.simulateTask(task.task_id, "success");
        onTaskPatched(updated);
      } else if (action === "simulate-failure") {
        const updated = await apiClient.simulateTask(task.task_id, "failure");
        onTaskPatched(updated);
      } else {
        const updated = await apiClient.retryTask(task.task_id, "frontend retry");
        onTaskPatched(updated);
      }

      await reloadArtifacts(task.task_id);
    } catch (err) {
      setActionError(
        getUserFacingErrorMessage(err, {
          isChinese,
          context: action === "retry" ? "retry" : "execution_run",
          fallback: action === "retry" ? getRetryErrorMessage("Action failed") : isChinese ? "操作失败，请稍后重试。" : "Action failed. Please try again."
        })
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function runClaim() {
    if (!task || !claimAgentId) {
      return;
    }
    setBusyAction("claim");
    setActionError(null);
    try {
      const updated = await apiClient.claimTask(task.task_id, claimAgentId, "claimed from dashboard");
      onTaskPatched(updated);
      await reloadArtifacts(task.task_id);
    } catch (err) {
      setActionError(getUserFacingErrorMessage(err, { isChinese, context: "claim", fallback: isChinese ? "认领失败。" : "Claim failed." }));
    } finally {
      setBusyAction(null);
    }
  }

  async function runHandoff() {
    if (!task || !task.current_agent_id || !handoffToAgentId) {
      return;
    }
    setBusyAction("handoff");
    setActionError(null);
    try {
      const updated = await apiClient.handoffTask(
        task.task_id,
        task.current_agent_id,
        handoffToAgentId,
        "handoff from dashboard"
      );
      onTaskPatched(updated);
      await reloadArtifacts(task.task_id);
    } catch (err) {
      setActionError(getUserFacingErrorMessage(err, { isChinese, context: "handoff", fallback: isChinese ? "交接失败。" : "Handoff failed." }));
    } finally {
      setBusyAction(null);
    }
  }

  async function runCopyResult(format: "md" | "txt") {
    if (!task) {
      return;
    }
    const content = buildTaskResultExportContent(task, format);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = content;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setResultActionMessage(isChinese ? "结果已复制到剪贴板。" : "Result copied to clipboard.");
    } catch {
      setResultActionMessage(isChinese ? "复制失败，请重试。" : "Copy failed. Please retry.");
    }
  }

  async function runExportResult(format: "md" | "txt") {
    if (!task) {
      return;
    }
    try {
      const file = await apiClient.exportTaskResult(task.task_id, format);
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setResultActionMessage(isChinese ? `已导出文件：${file.filename}` : `Exported: ${file.filename}`);
    } catch (err) {
      setResultActionMessage(getUserFacingErrorMessage(err, { isChinese, context: "tasks" }));
    }
  }

  return (
    <section className="nexus-panel p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionTaskDetail}</h3>
      {!task ? <p className="text-sm text-[#6b6860]">{isChinese ? "请先选择一个任务查看详细信息。" : "Choose a task to view details."}</p> : null}
      {task ? (
        <div className="space-y-3 text-sm">
          <p className="text-[#141413]">{task.objective}</p>
          <p data-testid="task-status-line" className="text-[#6b6860]">
            {task.task_id} • {isChinese ? "状态" : "status"}: {task.status} • {isChinese ? "完成进度" : "progress"}: {task.progress}%
          </p>

          <div className="grid gap-2 md:grid-cols-3">
            <InfoCard label={isChinese ? "优先级" : "Priority"} value={task.priority} />
            <InfoCard label={isChinese ? "当前负责人" : "Current Owner"} value={task.current_agent_id ?? (isChinese ? "尚未认领" : "unclaimed")} />
            <InfoCard label={isChinese ? "重试次数" : "Retries"} value={String(task.retry_count)} />
            <InfoCard label={isChinese ? "已分配智能体" : "Assigned Agents"} value={formatAgentList(task.assigned_agent_ids)} />
            <InfoCard label={isChinese ? "创建时间" : "Created"} value={formatTimestamp(task.created_at)} />
            <InfoCard label={isChinese ? "更新时间" : "Updated"} value={formatTimestamp(task.updated_at)} />
          </div>

          <div className="flex flex-wrap gap-2 rounded-2xl border border-[#ddd7ca] bg-[#fff8ef] p-2">
            <TabButton
              label={isChinese ? "概览" : "Overview"}
              isActive={showOverview}
              onClick={() => setActiveTab("overview")}
              testId="task-detail-tab-overview"
            />
            <TabButton
              label={isChinese ? "执行" : "Execution"}
              isActive={showExecution}
              onClick={() => setActiveTab("execution")}
              testId="task-detail-tab-execution"
            />
            <TabButton
              label={isChinese ? "协作记录" : "Coordination"}
              isActive={showCoordination}
              onClick={() => setActiveTab("coordination")}
              testId="task-detail-tab-coordination"
            />
          </div>

          {showExecution ? (
            <div className="space-y-3">
          {isAdminUser ? (
            <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3">
              <p className="mb-2 text-xs uppercase tracking-wide text-[#8a867d]">{text.executionQuickActionsTitle}</p>
              <div className="grid gap-2 rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 md:grid-cols-2">
                <div className="md:col-span-2 rounded-xl border border-[#ddd7ca] bg-[#fffaf0] p-3 text-xs text-[#6b6860]">
                  {hasUserApiKey
                    ? isChinese
                      ? "已检测到你的 AI API Key。点击执行后将优先走真实执行路径，默认不会自动回退到模拟结果。"
                      : "User AI API key detected: execution will use the real path first and will not fall back to simulation by default."
                    : isChinese
                      ? "未检测到你的 AI API Key；真实执行可能失败。请先在设置页配置 MODELSCOPE_ACCESS_TOKEN，或确认后端已配置执行密钥。"
                      : "No user AI API key detected. Real execution may fail. Set MODELSCOPE_ACCESS_TOKEN in Settings or confirm the backend execution key is configured."}
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{text.executionOwnershipTitle}</p>
                  <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "认领任务" : "Claim"}</p>
                  <div className="flex gap-2">
                    <select
                      data-testid="task-claim-agent-select"
                      value={claimAgentId}
                      onChange={(event) => setClaimAgentId(event.target.value)}
                      className="w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs"
                    >
                      <option value="">{isChinese ? "选择智能体" : "Select agent"}</option>
                      {agents.map((agent) => (
                        <option key={agent.agent_id} value={agent.agent_id}>
                          {getAgentLabelById(agent.agent_id)}
                        </option>
                      ))}
                    </select>
                    <button
                      data-testid="task-claim-button"
                      type="button"
                      onClick={runClaim}
                      disabled={busyAction !== null || !claimAgentId}
                      className="nexus-button-primary rounded-lg px-2 py-1 text-xs disabled:opacity-50"
                    >
                      {busyAction === "claim" ? "..." : isChinese ? "认领" : "Claim"}
                    </button>
                  </div>
                </div>

                <div>
                  <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "交接任务" : "Handoff"}</p>
                  <div className="flex gap-2">
                    <select
                      data-testid="task-handoff-target-select"
                      value={handoffToAgentId}
                      onChange={(event) => setHandoffToAgentId(event.target.value)}
                      className="w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs"
                    >
                      <option value="">{isChinese ? "选择目标智能体" : "Select target"}</option>
                      {agents
                        .filter((agent) => agent.agent_id !== task.current_agent_id)
                        .map((agent) => (
                          <option key={agent.agent_id} value={agent.agent_id}>
                            {getAgentLabelById(agent.agent_id)}
                          </option>
                        ))}
                    </select>
                    <button
                      data-testid="task-handoff-button"
                      type="button"
                      onClick={runHandoff}
                      disabled={busyAction !== null || !task.current_agent_id || !handoffToAgentId}
                      className="nexus-button-primary rounded-lg px-2 py-1 text-xs disabled:opacity-50"
                    >
                      {busyAction === "handoff" ? "..." : isChinese ? "交接" : "Handoff"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  data-testid="task-simulate-success-button"
                  type="button"
                  onClick={() => runAction("simulate-success")}
                  disabled={busyAction !== null}
                  className="rounded-lg border border-[#9bc5a7] bg-[#edf7ef] px-2 py-1 text-xs text-[#2f5d3e] disabled:opacity-50"
                >
                  {busyAction === "simulate-success" ? (isChinese ? "执行中..." : "Running...") : isChinese ? "模拟成功" : "Simulate Success"}
                </button>
                <button
                  data-testid="task-simulate-failure-button"
                  type="button"
                  onClick={() => runAction("simulate-failure")}
                  disabled={busyAction !== null}
                  className="rounded-lg border border-[#e5d0b4] bg-[#fff7ec] px-2 py-1 text-xs text-[#9a6a34] disabled:opacity-50"
                >
                  {busyAction === "simulate-failure" ? (isChinese ? "执行中..." : "Running...") : isChinese ? "模拟失败" : "Simulate Failure"}
                </button>
                <button
                  data-testid="task-retry-button"
                  type="button"
                  onClick={() => runAction("retry")}
                  disabled={busyAction !== null || task.status !== "failed"}
                  className="nexus-button-primary rounded-lg px-2 py-1 text-xs disabled:opacity-50"
                >
                  {busyAction === "retry" ? (isChinese ? "重试中..." : "Retrying...") : isChinese ? "重试任务" : "Retry Task"}
                </button>
              </div>
            </div>
          ) : null}

          {isAdminUser ? (
            <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3">
              <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{text.executionAdvancedTitle}</p>
              <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{text.executionSectionTitle}</p>
              <p className="mb-3 text-xs text-[#6b6860]">{text.executionSectionHint}</p>
              <div className="grid gap-2 md:grid-cols-2">
                <label className="text-xs text-[#6b6860]">
                  {text.executionModeLabel}
                  <select
                    value={executionMode}
                    onChange={(event) => setExecutionMode(event.target.value as ExecutionMode)}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                  >
                    <option value="single">{text.executionModeSingle}</option>
                    <option value="pipeline">{text.executionModePipeline}</option>
                    <option value="parallel">{text.executionModeParallel}</option>
                  </select>
                </label>
                <label className="text-xs text-[#6b6860]">
                  {text.executionErrorPolicyLabel}
                  <select
                    value={pipelineErrorPolicy}
                    onChange={(event) => setPipelineErrorPolicy(event.target.value as PipelineErrorPolicy)}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                  >
                    <option value="fail_fast">fail_fast</option>
                    <option value="continue">continue</option>
                  </select>
                </label>
                <label className="text-xs text-[#6b6860] md:col-span-2">
                  {text.executionAgentsLabel}
                  <input
                    value={pipelineAgentIdsText}
                    onChange={(event) => {
                      setPipelineAgentIdsText(event.target.value);
                      setPipelineAgentIdsDirty(true);
                    }}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                    placeholder={text.executionPipelinePlaceholder}
                  />
                  <div className="mt-2 flex flex-wrap gap-2">
                    {agents.map((agent) => {
                      const selected = pipelineAgentIdSet.has(agent.agent_id);
                      return (
                        <button
                          key={`pipeline-chip-${agent.agent_id}`}
                          type="button"
                          onClick={() => togglePipelineAgent(agent.agent_id)}
                          className={`rounded-full border px-3 py-1 text-[11px] transition ${
                            selected
                              ? "border-[#d97757] bg-[#fff4ee] text-[#b95535]"
                              : "border-[#d8d2c4] bg-[#fffcf6] text-[#6b6860] hover:bg-[#fff8ef]"
                          }`}
                        >
                          {getAgentLabelById(agent.agent_id)}
                        </button>
                      );
                    })}
                    <button
                      type="button"
                      onClick={selectRecommendedPipelineAgents}
                      className="rounded-full border border-[#d8d2c4] bg-[#f5f1e7] px-3 py-1 text-[11px] text-[#6b6860] hover:bg-[#ece7da]"
                    >
                      {isChinese ? "自动选择推荐智能体" : "Auto-select recommended agents"}
                    </button>
                  </div>
                </label>
                <label className="flex items-center gap-2 text-xs text-[#6b6860]">
                  <input
                    type="checkbox"
                    checked={allowFallback}
                    onChange={(event) => setAllowFallback(event.target.checked)}
                  />
                  {text.executionAllowFallbackLabel}
                </label>
                <p className="text-xs text-[#8a867d] md:col-span-2">
                  {isChinese
                    ? "默认关闭回退：仅当你手动启用后，真实执行失败才会切换为模拟结果。"
                    : "Fallback is off by default: real execution will only degrade to simulated output if you enable it explicitly."}
                </p>
                <label className="text-xs text-[#6b6860]">
                  {text.executionFallbackModeLabel}
                  <select
                    value={fallbackMode}
                    onChange={(event) => setFallbackMode(event.target.value as FallbackMode)}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                  >
                    <option value="simulate">simulate</option>
                    <option value="fail">fail</option>
                  </select>
                </label>
                <label className="text-xs text-[#6b6860]">
                  {text.executionArbitrationLabel}
                  <select
                    value={arbitrationMode}
                    onChange={(event) => setArbitrationMode(event.target.value as ArbitrationMode)}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                  >
                    <option value="off">off</option>
                    <option value="judge_on_conflict">judge_on_conflict</option>
                    <option value="judge_always">judge_always</option>
                  </select>
                </label>
                <label className="text-xs text-[#6b6860]">
                  {text.executionJudgeAgentLabel}
                  <input
                    value={judgeAgentId}
                    onChange={(event) => setJudgeAgentId(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                  />
                </label>
              </div>

            </div>
          ) : (
            <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3">
              <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "执行配置" : "Real execution"}</p>
              <p className="mb-3 text-xs text-[#6b6860]">
                {isChinese
                  ? "选择执行模式、点选已有智能体，预览后开始执行。"
                  : "Non-admin users only see the real execution path: choose a mode, pick existing agents, preview, then execute."}
              </p>
              <div className="grid gap-2 md:grid-cols-2">
                <label className="text-xs text-[#6b6860]">
                  {text.executionModeLabel}
                  <select
                    value={executionMode}
                    onChange={(event) => setExecutionMode(event.target.value as ExecutionMode)}
                    className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1"
                  >
                    <option value="single">{text.executionModeSingle}</option>
                    <option value="pipeline">{text.executionModePipeline}</option>
                    <option value="parallel">{text.executionModeParallel}</option>
                  </select>
                </label>
                <div className="md:col-span-2">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-[#6b6860]">{isChinese ? "选择执行智能体（可多选）" : text.executionAgentsLabel}</p>
                    <button
                      type="button"
                      onClick={selectRecommendedPipelineAgents}
                      className="rounded-full border border-[#d8d2c4] bg-[#f5f1e7] px-3 py-1 text-[11px] text-[#6b6860] hover:bg-[#ece7da]"
                    >
                      {isChinese ? "一键推荐" : "Auto-select"}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {agents.map((agent) => {
                      const selected = pipelineAgentIdSet.has(agent.agent_id);
                      return (
                        <button
                          key={`pipeline-chip-${agent.agent_id}`}
                          type="button"
                          onClick={() => togglePipelineAgent(agent.agent_id)}
                          className={`rounded-full border px-3 py-1 text-[11px] transition ${
                            selected
                              ? "border-[#d97757] bg-[#fff4ee] text-[#b95535]"
                              : "border-[#d8d2c4] bg-[#fffcf6] text-[#6b6860] hover:bg-[#fff8ef]"
                          }`}
                        >
                          {getAgentLabelById(agent.agent_id)}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-xs text-[#8a867d]">
                    {isChinese ? "已选智能体：" : "Selected agents: "}
                    {pipelineAgentIds.length > 0 ? pipelineAgentIds.map((agentId) => getAgentLabelById(agentId)).join(", ") : isChinese ? "暂无" : "none"}
                  </p>
                </div>
                {task.status === "failed" ? (
                  <button
                    data-testid="task-retry-button"
                    type="button"
                    onClick={() => runAction("retry")}
                    disabled={busyAction !== null}
                    className="nexus-button-primary rounded-lg px-2 py-1 text-xs disabled:opacity-50 md:col-span-2"
                  >
                    {busyAction === "retry" ? (isChinese ? "重试中..." : "Retrying...") : isChinese ? "重试任务" : "Retry Task"}
                  </button>
                ) : null}
              </div>
            </div>
          )}

            <div className="mt-3 flex flex-wrap gap-2">
              <button
                data-testid="task-preview-execution-button"
                type="button"
                onClick={runExecutionPreview}
                disabled={busyAction !== null}
                className="nexus-button-ghost rounded-lg px-3 py-1.5 text-xs disabled:opacity-50"
              >
                {busyAction === "preview" ? text.executionPreviewingButton : text.executionPreviewButton}
              </button>
              <button
                data-testid="task-execute-button"
                type="button"
                onClick={runExecuteTask}
                disabled={busyAction !== null || !executionPreview || isPreviewStale}
                className="nexus-button-primary rounded-lg px-3 py-1.5 text-xs disabled:opacity-50"
              >
                {busyAction === "execute" ? text.executionRunningButton : text.executionRunButton}
              </button>
            </div>

            {executionError ? <p className="mt-2 text-xs text-[#c0453a]">{executionError}</p> : null}

            {!executionPreview ? (
              <div className="mt-3 rounded-xl border border-dashed border-[#d8d2c4] bg-[#f7f2e8] p-3 text-xs text-[#6b6860]">
                {text.executionPreviewEmpty}
              </div>
            ) : (
              <div data-testid="task-execution-preview-panel" className="mt-3 space-y-2 rounded-xl border border-[#ddd7ca] bg-[#fff8ef] p-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-[#3e3a35]">{text.executionPreviewTitle}</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-[11px] text-[#6b6860]">
                      {text.executionPreviewSteps}: {executionPreview.steps.length}
                    </span>
                    <span className="rounded-full border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-[11px] text-[#6b6860]">
                      {text.executionPreviewEvents}: {executionPreview.estimated_events.length}
                    </span>
                    <span className="rounded-full border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-[11px] text-[#6b6860]">
                      {text.executionPreviewWarnings}: {executionPreview.preview_warnings.length}
                    </span>
                  </div>
                </div>
                {isPreviewStale ? (
                  <p className="rounded-lg border border-[#e5d0b4] bg-[#fff7ec] px-2 py-2 text-[#9a6a34]">{text.executionPreviewStale}</p>
                ) : null}
                <p className="text-[#6b6860]">
                  {text.executionPreviewSummary}: {isChinese ? "模式" : "mode"}={executionPreview.execution_mode} • {isChinese ? "策略" : "policy"}={executionPreview.pipeline_error_policy} • fallback={String(executionPreview.allow_fallback)}
                </p>
                <div>
                  <p className="mb-1 text-[#8a867d]">{text.executionPreviewSteps}</p>
                  <ul className="space-y-1">
                    {executionPreview.steps.map((step) => (
                      <li key={`${step.step}-${step.agent_id}`} className="rounded border border-[#ddd7ca] bg-[#fffcf6] px-2 py-1 text-[#3e3a35]">
                        #{step.step} {getAgentLabelById(step.agent_id)} ({step.agent_role}) - {step.transition_action}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-[#8a867d]">{text.executionPreviewEvents}</p>
                  <ul className="space-y-1">
                    {executionPreview.estimated_events.map((event, index) => (
                      <li key={`${event.event_type}-${index}`} className="text-[#6b6860]">
                        {event.event_type} [{event.condition}]
                        {event.step ? ` #${event.step}` : ""}
                        {event.agent_id ? ` ${getAgentLabelById(event.agent_id)}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-[#8a867d]">{text.executionPreviewWarnings}</p>
                  {executionPreview.preview_warnings.length === 0 ? (
                    <p className="text-[#6b6860]">{text.executionNoWarnings}</p>
                  ) : (
                    <ul className="space-y-1">
                      {executionPreview.preview_warnings.map((warning, index) => (
                        <li key={`${warning.code}-${index}`} className="text-[#6b6860]">
                          {warning.code}: {warning.message}
                          {warning.applies_to_step ? (isChinese ? `（步骤 ${warning.applies_to_step}）` : ` (step ${warning.applies_to_step})`) : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}

          {actionError ? <p className="text-xs text-[#c0453a]">{actionError}</p> : null}
            </div>
          ) : null}

          {showOverview ? (
            <>
          <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-xs text-[#3e3a35]" data-testid="task-explanation-panel">
            <p className="mb-2 text-xs uppercase tracking-wide text-[#8a867d]">{text.explanationSectionTitle}</p>
            {routingExplanation || arbitrationExplanation ? (
              <div className="space-y-2">
                {routingExplanation ? (
                  <div className="rounded-lg border border-[#ddd7ca] bg-[#fff8ef] p-2" data-testid="task-routing-explanation">
                    <p className="font-medium text-[#141413]">{text.routingExplanationTitle}</p>
                    <p className="mt-1 text-[#6b6860]">{localizeCollaborationText(routingExplanation.reason)}</p>
                    {routingExplanation.selectedAgentIds.length > 0 ? (
                      <p className="mt-1 text-[#6b6860]">
                        {isChinese ? "入选智能体" : "Selected agents"}: {routingExplanation.selectedAgentIds.map((agentId) => getAgentLabelById(agentId)).join(", ")}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {arbitrationExplanation ? (
                  <div className="rounded-lg border border-[#ddd7ca] bg-[#fff8ef] p-2" data-testid="task-arbitration-explanation">
                    <p className="font-medium text-[#141413]">{text.arbitrationExplanationTitle}</p>
                    <p className="mt-1 text-[#6b6860]">{localizeCollaborationText(arbitrationExplanation.selectionBasis)}</p>
                    {arbitrationExplanation.selectedSummary ? (
                      <p className="mt-1 text-[#6b6860]">
                        {isChinese ? "最终摘要" : "Selected summary"}: {arbitrationExplanation.selectedSummary}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-[#6b6860]">{text.explanationEmpty}</p>
            )}
          </div>

          {(() => {
            const taskError = getTaskResultErrorSummary(task);
            if (!taskError) {
              return null;
            }
            return (
              <div className="rounded-xl border border-[#e6c8ae] bg-[#fff6eb] p-3 text-xs text-[#8a5f33]">
                <p className="font-medium text-[#7a5030]">{isChinese ? "执行提示" : "Execution note"}</p>
                <p className="mt-1 leading-relaxed">{taskError.userMessage}</p>
                {taskError.retryable !== null ? (
                  <p className="mt-2 text-[#6b6860]">
                    {isChinese ? "是否适合重试" : "Retryable"}: {taskError.retryable ? (isChinese ? "是" : "yes") : (isChinese ? "否" : "no")}
                  </p>
                ) : null}
              </div>
            );
          })()}

          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "执行结果" : "Result"}</p>
            {task.result ? (
              <div className="mb-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => {
                    void runCopyResult("md");
                  }}
                  className="rounded-lg border border-[#d8d2c4] bg-[#f4efe4] px-2 py-1 text-[11px] text-[#6b6860]"
                >
                  {isChinese ? "复制为 Markdown" : "Copy as Markdown"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void runExportResult("md");
                  }}
                  className="rounded-lg border border-[#9bc5a7] bg-[#edf7ef] px-2 py-1 text-[11px] text-[#2f5d3e]"
                >
                  {isChinese ? "导出 .md" : "Export .md"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void runExportResult("txt");
                  }}
                  className="rounded-lg border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-[11px] text-[#6b6860]"
                >
                  {isChinese ? "导出 .txt" : "Export .txt"}
                </button>
              </div>
            ) : null}
            {task.result ? (
              <div className="space-y-2">
                <div data-testid="task-final-output" className="max-h-[600px] overflow-y-auto rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-xs text-[#3e3a35] relative">
                  <div className="whitespace-pre-wrap break-words leading-relaxed text-[#3e3a35]">{getUserFacingResultContent(task.result)}</div>
                </div>
                <p className="text-[10px] text-[#8a867d] italic">{isChinese ? "提示：内容较长时可滚动查看完整结果" : "Tip: Scroll to view full result when content is long"}</p>
              </div>
            ) : (
              <p className="text-xs text-[#6b6860]">{isChinese ? "暂无执行结果输出。" : "No result output yet."}</p>
            )}
            {resultActionMessage ? <p className="mt-2 text-xs text-[#6b6860]">{resultActionMessage}</p> : null}
          </div>

          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "任务分解" : "Task Decomposition"}</p>
            {!decomposition ? (
              <p className="text-xs text-[#6b6860]">{isChinese ? "未找到任务分解元数据。" : "No decomposition metadata found."}</p>
            ) : (
              <div className="space-y-3 rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-xs">
                <p className="text-[#6b6860]">
                  mode: {decomposition.mode} {decomposition.template ? `• template: ${decomposition.template}` : ""}
                </p>
                {decomposition.workflow_run || decomposition.dispatch_state ? (
                  <div className="rounded-lg border border-[#ddd7ca] bg-[#fff8ef] p-2" data-testid="task-workflow-runtime-panel">
                    <p className="font-medium text-[#141413]">{isChinese ? "调度运行态" : "Workflow runtime"}</p>
                    {decomposition.workflow_run ? (
                      <p className="mt-1 text-[#6b6860]">
                        run={decomposition.workflow_run.workflow_run_id ?? "-"} • scheduler={decomposition.workflow_run.scheduler_mode ?? "-"} • queue={decomposition.workflow_run.queue_backend ?? "-"}
                      </p>
                    ) : null}
                    {decomposition.dispatch_state ? (
                      <div className="mt-2 grid gap-2 md:grid-cols-5">
                        <InfoCard label={isChinese ? "就绪" : "Ready"} value={String(decomposition.dispatch_state.ready_count ?? 0)} />
                        <InfoCard label={isChinese ? "运行中" : "Running"} value={String(decomposition.dispatch_state.running_count ?? 0)} />
                        <InfoCard label={isChinese ? "阻塞" : "Blocked"} value={String(decomposition.dispatch_state.blocked_count ?? 0)} />
                        <InfoCard label={isChinese ? "已完成" : "Completed"} value={String(decomposition.dispatch_state.completed_count ?? 0)} />
                        <InfoCard label={isChinese ? "失败" : "Failed"} value={String(decomposition.dispatch_state.failed_count ?? 0)} />
                      </div>
                    ) : null}
                    <p className="mt-2 text-[#8a867d]">
                      {isChinese ? "当前就绪队列" : "Current ready queue"}: {decomposition.ready_queue && decomposition.ready_queue.length > 0 ? decomposition.ready_queue.join(", ") : isChinese ? "空" : "empty"}
                    </p>
                  </div>
                ) : null}
                <ul className="space-y-2">
                  {(decomposition.dag_nodes && decomposition.dag_nodes.length > 0 ? decomposition.dag_nodes : decomposition.subtasks).map((step) => (
                    <li key={"node_id" in step ? step.node_id : step.step_id} className="rounded-lg border border-[#ddd7ca] bg-[#fff8ef] p-2">
                      <p className="font-medium text-[#141413]">{step.title}</p>
                      <p className="mt-1 text-[#6b6860]">
                        {"node_id" in step ? step.node_id : step.step_id} • {step.status}
                        {"dispatch_state" in step ? ` • ${step.dispatch_state}` : ""} • {step.assigned_agent_id ?? (isChinese ? "未分配" : "unassigned")}
                      </p>
                      {"attempt_count" in step && typeof step.attempt_count === "number" ? (
                        <p className="mt-1 text-[#8a867d]">{isChinese ? "尝试次数" : "Attempts"}: {step.attempt_count}</p>
                      ) : null}
                      {"last_error_message" in step && step.last_error_message ? (
                        <p className="mt-1 text-[#c0453a]">{isChinese ? "最近错误" : "Latest error"}: {step.last_error_message}</p>
                      ) : null}
                      {step.depends_on.length > 0 ? (
                        <p className="mt-1 text-[#8a867d]">{isChinese ? "依赖" : "depends on"}: {step.depends_on.join(", ")}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
            </>
          ) : null}

          {showCoordination ? (
            <>
          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "交接历史" : "Handoff History"}</p>
            {task.handoff_history && task.handoff_history.length > 0 ? (
              <ul className="space-y-1 rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-xs text-[#3e3a35]">
                {task.handoff_history.map((item, index) => (
                  <li key={`${item.handed_off_at}-${index}`}>
                    {item.from_agent_id} → {item.to_agent_id}
                    {item.reason ? ` (${item.reason})` : ""} • {formatTimestamp(item.handed_off_at)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#6b6860]">{isChinese ? "暂无交接记录。" : "No handoffs yet."}</p>
            )}
          </div>

          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "元数据" : "Metadata"}</p>
            <pre className="overflow-auto rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-xs text-[#3e3a35]">
              {toPrettyJson(task.metadata)}
            </pre>
          </div>

          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "尝试记录" : "Attempts"}</p>
            {!attempts || attempts.items.length === 0 ? (
              <p className="text-xs text-[#6b6860]">{isChinese ? "暂无尝试记录。" : "No attempts recorded."}</p>
            ) : (
              <ul className="space-y-1 text-xs text-[#3e3a35]">
                {attempts.items.map((item, index) => (
                  <li key={`${item.timestamp}-${index}`}>
                    #{item.attempt_number} {item.outcome}
                    {item.reason ? ` - ${item.reason}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-[#8a867d]">{isChinese ? "共识" : "Consensus"}</p>
            {!consensus || !consensus.consensus ? (
              <p className="text-xs text-[#6b6860]">{isChinese ? "暂未形成共识。" : "No consensus computed yet."}</p>
            ) : (
              <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs text-[#3e3a35]">
                <p>decided_by: {consensus.consensus.decided_by}</p>
                <p>conflict: {String(consensus.consensus.conflict_detected)}</p>
                <p>reason: {consensus.consensus.reason}</p>
                {consensusExplanation ? <p>explanation: {consensusExplanation.summary}</p> : null}
              </div>
            )}
            {consensusExplanation ? (
              <div className="mt-2 rounded-xl border border-[#ddd7ca] bg-[#fff8ef] p-2 text-xs text-[#3e3a35]" data-testid="task-consensus-explanation">
                <p className="font-medium text-[#141413]">{text.consensusExplanationTitle}</p>
                <p className="mt-1 text-[#6b6860]">{localizeCollaborationText(consensusExplanation.summary)}</p>
                {consensusExplanation.selectedAgentId ? (
                  <p className="mt-1 text-[#6b6860]">
                    {isChinese ? "选中智能体" : "Selected agent"}: {getAgentLabelById(consensusExplanation.selectedAgentId)}
                  </p>
                ) : null}
              </div>
            ) : null}
            {consensus && consensus.proposals.length > 0 ? (
              <div className="mt-2 space-y-2">
                <ul className="space-y-1 text-xs text-[#6b6860]">
                  {consensus.proposals.map((proposal, index) => (
                    <li key={`${proposal.agent_id}-${index}`}>
                      {proposal.agent_id} • confidence {proposal.confidence} • {formatTimestamp(proposal.submitted_at)}
                    </li>
                  ))}
                </ul>

                {consensusRows.length > 0 ? (
                  <div className="overflow-auto rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2">
                    <p className="mb-2 text-xs text-[#6b6860]">{isChinese ? "方案与决策对照" : "Proposal vs decision snapshot"}</p>
                    <table className="min-w-full text-left text-xs text-[#3e3a35]">
                      <thead className="text-[#8a867d]">
                        <tr>
                          <th className="px-2 py-1">{isChinese ? "字段" : "Key"}</th>
                          <th className="px-2 py-1">{isChinese ? "决策值" : "Decision"}</th>
                          <th className="px-2 py-1">{isChinese ? "候选方案" : "Proposals"}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {consensusRows.map((row) => (
                          <tr key={row.key} className="border-t border-[#e7e1d5] align-top">
                            <td className="px-2 py-1 text-[#6b6860]">{row.key}</td>
                            <td className="px-2 py-1 text-[#141413]">{row.decisionValue}</td>
                            <td className="space-y-1 px-2 py-1">
                              {row.proposals.map((item) => (
                                <div key={`${row.key}-${item.agentId}`}>
                                  <span className={item.matchesDecision ? "text-[#3f6b4a]" : "text-[#6b6860]"}>
                                    {item.agentId}: {item.value}
                                  </span>
                                </div>
                              ))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function TabButton({
  label,
  isActive,
  onClick,
  testId
}: {
  label: string;
  isActive: boolean;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      data-testid={testId}
      type="button"
      onClick={onClick}
      className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
        isActive ? "bg-[#141413] text-[#f5f3ec]" : "bg-[#f4efe4] text-[#6b6860] hover:bg-[#ece6d9]"
      }`}
    >
      {label}
    </button>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs">
      <p className="text-[#8a867d]">{label}</p>
      <p className="mt-1 text-[#141413]">{value}</p>
    </div>
  );
}


