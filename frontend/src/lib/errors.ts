import { ApiClientError } from "@/lib/api/api-error";

export type ErrorContext =
  | "backend"
  | "agents"
  | "tasks"
  | "task"
  | "events"
  | "websocket"
  | "retry"
  | "claim"
  | "handoff"
  | "execution_preview"
  | "execution_run";

interface ErrorMessageOptions {
  isChinese: boolean;
  context: ErrorContext;
  fallback?: string;
}

interface ConnectionStatusCopy {
  title: string;
  detail: string;
  tone: "neutral" | "success" | "warning";
}

function extractEmbeddedDetail(raw: string): string {
  const normalized = raw.trim();
  const httpJsonMatch = normalized.match(/^HTTP\s+\d+\s*:\s*(\{.*})$/);
  if (httpJsonMatch) {
    try {
      const parsed = JSON.parse(httpJsonMatch[1]) as { detail?: unknown; user_message?: unknown };
      if (typeof parsed.user_message === "string" && parsed.user_message.trim()) {
        return parsed.user_message.trim();
      }
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
    } catch {
      return normalized;
    }
  }
  return normalized;
}

function getNetworkMessage(isChinese: boolean, context: ErrorContext): string {
  const map = {
    backend: isChinese
      ? "无法连接后端服务。请确认 `http://localhost:8000` 已启动，再重试。"
      : "Cannot reach the backend service. Confirm `http://localhost:8000` is running.",
    agents: isChinese
      ? "无法加载智能体列表。请先确认后端服务正常运行。"
      : "Unable to load the agent list. Confirm the backend service is running.",
    tasks: isChinese
      ? "无法加载任务列表。请刷新页面，或确认后端服务已启动。"
      : "Unable to load tasks. Refresh the page or confirm the backend service is running.",
    task: isChinese
      ? "无法加载任务详情。请刷新页面，或确认该任务仍然存在。"
      : "Unable to load task details. Refresh the page or confirm the task still exists.",
    events: isChinese
      ? "无法获取事件历史。任务可能仍可访问，但事件接口当前不可用。"
      : "Unable to load event history. The task may still exist, but the events endpoint is unavailable.",
    websocket: isChinese
      ? "实时事件连接暂不可用。系统会自动重连，你也可以稍后手动刷新。"
      : "Live event streaming is temporarily unavailable. The app will retry automatically, or you can refresh later.",
    retry: isChinese
      ? "重试请求未成功发送。请确认后端在线后再试。"
      : "Retry request could not be sent. Confirm the backend is online and try again.",
    claim: isChinese
      ? "认领请求发送失败。请确认后端在线后再试。"
      : "The claim request could not be sent. Confirm the backend is online and try again.",
    handoff: isChinese
      ? "交接请求发送失败。请确认后端在线后再试。"
      : "The handoff request could not be sent. Confirm the backend is online and try again.",
    execution_preview: isChinese
      ? "无法预览执行计划。请确认后端在线，并检查当前执行配置。"
      : "Unable to preview the execution plan. Confirm the backend is online and review the execution settings.",
    execution_run: isChinese
      ? "无法发起执行。请确认后端在线，并检查当前执行配置。"
      : "Unable to start execution. Confirm the backend is online and review the execution settings."
  } satisfies Record<ErrorContext, string>;

  return map[context];
}

function mapHttpDetail(detail: string, isChinese: boolean, context: ErrorContext): string | null {
  const normalized = detail.toLowerCase();
  if (normalized.includes("retry limit reached")) {
    return isChinese
      ? "已达到重试上限。请先提高 max_retries 或排查失败原因后再重试。"
      : "Retry limit reached. Increase max_retries or resolve the failure cause before retrying.";
  }
  if (normalized.includes("only failed tasks can be retried")) {
    return isChinese
      ? "任务当前不是失败状态，仅失败任务可执行重试。"
      : "Only failed tasks can be retried right now.";
  }
  if (normalized.includes("task already claimed by another agent")) {
    return isChinese
      ? "该任务已被其他智能体认领，请先查看当前持有者。"
      : "This task is already claimed by another agent. Check the current owner first.";
  }
  if (normalized.includes("task is not currently owned by from_agent_id")) {
    return isChinese
      ? "当前任务持有者与交接发起者不一致，请刷新后重试。"
      : "The current task owner does not match the handoff initiator. Refresh and try again.";
  }
  if (normalized.includes("agent not found") || normalized.includes("target agent not found")) {
    return isChinese
      ? "目标智能体不存在或尚未注册，请检查 Agent ID。"
      : "The target agent does not exist or is not registered. Check the agent ID.";
  }
  if (normalized.includes("task not found")) {
    return isChinese
      ? "任务不存在或已被清理。请返回任务台重新选择。"
      : "The task was not found or may have been cleared. Return to the tasks workspace and select another task.";
  }
  if (normalized.includes("invalid time range") || normalized.includes("invalid cursor") || normalized.includes("invalid preview payload")) {
    return isChinese
      ? "请求参数无效，请检查当前输入后再试。"
      : "The request parameters are invalid. Review the current inputs and try again.";
  }
  if (normalized.includes("missing api key") || normalized.includes("unsupported execution provider")) {
    return isChinese
      ? "真实执行配置不完整。请检查模型提供方、模型名称和 API Key。"
      : "Real execution is not configured correctly. Check the provider, model, and API key.";
  }
  if (normalized.includes("missing or invalid api key")) {
    return isChinese
      ? "当前请求缺少后端 API Key，或所填 Key 无效。请先在侧边栏配置 Backend API Key。"
      : "This request is missing a valid backend API key. Configure the Backend API key in the sidebar first.";
  }
  if (normalized.includes("insufficient role for this operation") || normalized.includes("requires one of:")) {
    return isChinese
      ? "当前账号权限不足，该操作已被限制为只读或管理员专用。"
      : "Your current role does not allow this operation. The action is read-only or admin-only.";
  }
  if (normalized.includes("provider returned empty content") || normalized.includes("execution produced no successful step")) {
    return isChinese
      ? "模型本次没有返回可用结果。你可以重试，或启用回退策略继续当前任务。"
      : "The model did not return a usable result. Retry, or enable fallback to continue the task.";
  }
  if (normalized.includes("provider unavailable") || normalized.includes("provider call failed")) {
    return isChinese
      ? "模型服务暂时不可用。你可以稍后重试，或启用回退策略继续当前流程。"
      : "The model provider is temporarily unavailable. Retry later, or enable fallback to continue the workflow.";
  }

  if (context === "events" && normalized.includes("websocket")) {
    return getNetworkMessage(isChinese, "websocket");
  }

  return null;
}

export function getUserFacingErrorMessage(error: unknown, options: ErrorMessageOptions): string {
  const { isChinese, context, fallback } = options;

  if (error instanceof ApiClientError) {
    if (error.userMessage && error.userMessage.trim()) {
      return error.userMessage;
    }
    if (error.kind === "network") {
      return getNetworkMessage(isChinese, context);
    }
    if (error.detail) {
      return mapHttpDetail(error.detail, isChinese, context) ?? extractEmbeddedDetail(error.detail);
    }
    if (typeof error.status === "number") {
      return isChinese ? `请求失败（HTTP ${error.status}）。请稍后重试。` : `Request failed (HTTP ${error.status}). Please try again.`;
    }
  }

  const raw = extractEmbeddedDetail(error instanceof Error ? error.message : String(error ?? ""));
  if (!raw) {
    return fallback ?? (isChinese ? "操作未成功完成，请稍后重试。" : "The action could not be completed. Please try again.");
  }

  const normalized = raw.toLowerCase();
  if (normalized.includes("failed to fetch") || normalized.includes("fetch failed") || normalized.includes("networkerror")) {
    return getNetworkMessage(isChinese, context);
  }
  if (normalized.includes("ws_connection_failed") || normalized.includes("ws_connection_interrupted")) {
    return getNetworkMessage(isChinese, "websocket");
  }

  return mapHttpDetail(raw, isChinese, context) ?? raw;
}

export function getEventConnectionCopy(
  connectionState: "idle" | "connecting" | "connected" | "reconnecting",
  isChinese: boolean,
  hasError: boolean
): ConnectionStatusCopy {
  if (connectionState === "connected") {
    return {
      title: isChinese ? "实时连接已建立" : "Live connection active",
      detail: isChinese ? "新事件会自动追加到事件流。" : "New events will appear in the stream automatically.",
      tone: "success"
    };
  }

  if (connectionState === "connecting") {
    return {
      title: isChinese ? "正在连接实时事件" : "Connecting to live events",
      detail: isChinese ? "首次进入任务时会先拉取历史事件，再连接实时推送。" : "The app first loads historical events, then connects to live updates.",
      tone: "neutral"
    };
  }

  if (connectionState === "reconnecting") {
    return {
      title: isChinese ? "实时连接中断，正在自动重连" : "Live connection interrupted, retrying",
      detail: hasError
        ? isChinese
          ? "历史事件仍可手动刷新查看，系统会持续自动重连。"
          : "Historical events can still be refreshed manually while the app keeps retrying."
        : isChinese
          ? "正在重新建立 WebSocket 连接。"
          : "Re-establishing the WebSocket connection.",
      tone: "warning"
    };
  }

  return {
    title: isChinese ? "尚未开始监听实时事件" : "Live event stream not started",
    detail: isChinese ? "选择任务后，系统会自动加载历史记录并连接实时推送。" : "Once a task is selected, the app will load history and connect to live updates.",
    tone: "neutral"
  };
}

