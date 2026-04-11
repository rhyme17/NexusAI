import {
  Agent,
  AgentRegisterPayload,
  AuthResponse,
  AuthUser,
  BusMessage,
  CreateInvitePayload,
  CreateTaskPayload,
  DeleteOwnAccountResponse,
  HealthStatusResponse,
  InviteCode,
  LoginUserPayload,
  ResetUserPasswordPayload,
  RegisterUserPayload,
  Task,
  TaskAttemptsResponse,
  TaskConsensusResponse,
  TaskEventsResponse,
  TaskExecutionPreviewResponse,
  TaskExecutionRequest,
  TaskResultExportFormat,
  MessageType,
  TaskStatus,
  UpdateUserStatusPayload
} from "./types";
import { ApiClientError } from "./api-error";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const BACKEND_API_KEY_STORAGE_KEY = "nexusai.backend_api_key";
const AUTH_TOKEN_STORAGE_KEY = "nexusai.auth_token";
export const AUTH_TOKEN_COOKIE_NAME = "nexusai_auth_token";
const CURRENT_USER_CACHE_TTL_MS = 10000;

let currentUserCache: { token: string; user: AuthUser; cachedAt: number } | null = null;
let currentUserInFlight: { token: string; promise: Promise<AuthUser> } | null = null;

function writeAuthCookie(token: string): void {
  if (typeof document === "undefined") {
    return;
  }
  const encoded = encodeURIComponent(token);
  document.cookie = `${AUTH_TOKEN_COOKIE_NAME}=${encoded}; Path=/; SameSite=Lax; Max-Age=${60 * 60 * 24 * 7}`;
}

function clearAuthCookie(): void {
  if (typeof document === "undefined") {
    return;
  }
  document.cookie = `${AUTH_TOKEN_COOKIE_NAME}=; Path=/; SameSite=Lax; Max-Age=0`;
}

export { ApiClientError };

function resetCurrentUserCache() {
  currentUserCache = null;
  currentUserInFlight = null;
}

export function getStoredBackendApiKey(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const stored = window.localStorage.getItem(BACKEND_API_KEY_STORAGE_KEY);
  return stored?.trim() ?? "";
}

export function setStoredBackendApiKey(next: string): string {
  const normalized = next.trim();
  if (typeof window !== "undefined") {
    if (normalized) {
      window.localStorage.setItem(BACKEND_API_KEY_STORAGE_KEY, normalized);
    } else {
      window.localStorage.removeItem(BACKEND_API_KEY_STORAGE_KEY);
    }
  }
  return normalized;
}

export function clearStoredBackendApiKey(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(BACKEND_API_KEY_STORAGE_KEY);
  }
}

export function getStoredAuthToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)?.trim() ?? "";
}

export function setStoredAuthToken(token: string): string {
  const normalized = token.trim();
  if (typeof window !== "undefined") {
    if (normalized) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, normalized);
      writeAuthCookie(normalized);
    } else {
      window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      clearAuthCookie();
    }
  }
  resetCurrentUserCache();
  return normalized;
}

export function clearStoredAuthToken(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    clearAuthCookie();
  }
  resetCurrentUserCache();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function readDetail(data: unknown): string | undefined {
  if (!isRecord(data)) {
    return undefined;
  }
  const detail = data.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (isRecord(detail)) {
    if (typeof detail.message === "string") {
      return detail.message;
    }
    if (typeof detail.detail === "string") {
      return detail.detail;
    }
  }
  return undefined;
}

function readUserMessage(data: unknown): string | undefined {
  if (!isRecord(data)) {
    return undefined;
  }
  if (typeof data.user_message === "string") {
    return data.user_message;
  }
  const detail = data.detail;
  if (isRecord(detail) && typeof detail.user_message === "string") {
    return detail.user_message;
  }
  return undefined;
}

async function buildHttpError(response: Response): Promise<ApiClientError> {
  const rawBody = await response.text();
  let parsedBody: unknown = undefined;
  if (rawBody) {
    try {
      parsedBody = JSON.parse(rawBody) as unknown;
    } catch {
      parsedBody = rawBody;
    }
  }

  const detail = readDetail(parsedBody) ?? (typeof parsedBody === "string" ? parsedBody : undefined);
  const userMessage = readUserMessage(parsedBody);
  const message = detail ? `HTTP ${response.status}: ${detail}` : `HTTP ${response.status}`;
  return new ApiClientError({
    message,
    kind: "http",
    status: response.status,
    detail,
    userMessage,
    data: parsedBody
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    applyStoredAuthHeaders(headers);
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store"
    });
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    const message = error instanceof Error ? error.message : "Network request failed";
    throw new ApiClientError({
      message,
      kind: "network",
      detail: message
    });
  }

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return (await response.json()) as T;
}

function applyStoredAuthHeaders(headers: Headers): void {
  const storedBackendApiKey = getStoredBackendApiKey();
  if (storedBackendApiKey && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", storedBackendApiKey);
  }
  const authToken = getStoredAuthToken();
  if (authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
}

function getCurrentUserCached(): Promise<AuthUser> {
  const token = getStoredAuthToken();
  const now = Date.now();

  if (currentUserCache && currentUserCache.token === token && now - currentUserCache.cachedAt < CURRENT_USER_CACHE_TTL_MS) {
    return Promise.resolve(currentUserCache.user);
  }

  if (currentUserInFlight && currentUserInFlight.token === token) {
    return currentUserInFlight.promise;
  }

  const requestPromise = request<AuthUser>("/api/auth/me")
    .then((user) => {
      currentUserCache = { token, user, cachedAt: Date.now() };
      return user;
    })
    .catch((error) => {
      if (currentUserCache?.token === token) {
        currentUserCache = null;
      }
      throw error;
    })
    .finally(() => {
      if (currentUserInFlight?.token === token) {
        currentUserInFlight = null;
      }
    });

  currentUserInFlight = { token, promise: requestPromise };
  return requestPromise;
}

export const apiClient = {
  getHealth: () => request<HealthStatusResponse>("/health"),
  registerUser: (payload: RegisterUserPayload) =>
    request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  loginUser: (payload: LoginUserPayload) =>
    request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getCurrentUser: () => getCurrentUserCached(),
  logoutUser: () =>
    request<{ status: string }>("/api/auth/logout", {
      method: "POST"
    }),
  deleteOwnAccount: () =>
    request<DeleteOwnAccountResponse>("/api/auth/me", {
      method: "DELETE"
    }),
  listInvites: () => request<InviteCode[]>("/api/auth/invites"),
  createInvite: (payload: CreateInvitePayload) =>
    request<InviteCode>("/api/auth/invites", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  revokeInvite: (code: string) =>
    request<{ status: string }>(`/api/auth/invites/${encodeURIComponent(code)}`, {
      method: "DELETE"
    }),
  listUsers: () => request<AuthUser[]>("/api/auth/users"),
  updateUserStatus: (username: string, payload: UpdateUserStatusPayload) =>
    request<AuthUser>(`/api/auth/users/${encodeURIComponent(username)}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  resetUserPassword: (username: string, payload: ResetUserPasswordPayload) =>
    request<AuthUser>(`/api/auth/users/${encodeURIComponent(username)}/reset-password`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listTasks: () => request<Task[]>("/api/tasks"),
  getTask: (taskId: string) => request<Task>(`/api/tasks/${taskId}`),
  createTask: (payload: CreateTaskPayload) =>
    request<Task>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listAgents: (options?: { skill?: string; status?: "online" | "offline" | "busy" }) => {
    const params = new URLSearchParams();
    if (options?.skill) {
      params.set("skill", options.skill);
    }
    if (options?.status) {
      params.set("status", options.status);
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Agent[]>(`/api/agents${suffix}`);
  },
  registerAgent: (payload: AgentRegisterPayload) =>
    request<Agent>("/api/agents", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateAgentStatus: (agentId: string, status: "online" | "offline" | "busy") =>
    request<Agent>(`/api/agents/${agentId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    }),
  clearServerData: (options?: { keepDefaultAgents?: boolean; clearEventsOnly?: boolean; restoreSeed?: boolean }) => {
    const params = new URLSearchParams();
    params.set("keep_default_agents", String(options?.keepDefaultAgents ?? true));
    params.set("clear_events_only", String(options?.clearEventsOnly ?? false));
    params.set("restore_seed", String(options?.restoreSeed ?? false));
    return request<{ status: string; seed_restored?: boolean; counts?: Record<string, number> }>(
      `/api/debug/storage/clear?${params.toString()}`,
      {
        method: "POST"
      }
    );
  },
  listTaskEvents: (
    taskId: string,
    options?: {
      limit?: number;
      sort?: "asc" | "desc";
      types?: MessageType[];
      from?: string;
      to?: string;
    }
  ) => {
    const params = new URLSearchParams();
    params.set("limit", String(options?.limit ?? 100));
    params.set("sort", options?.sort ?? "desc");
    options?.types?.forEach((type) => params.append("type", type));
    if (options?.from) {
      params.set("from", options.from);
    }
    if (options?.to) {
      params.set("to", options.to);
    }
    return request<BusMessage[]>(`/api/tasks/${taskId}/events?${params.toString()}`);
  },
  listTaskEventsMeta: (
    taskId: string,
    options?: {
      limit?: number;
      sort?: "asc" | "desc";
      types?: MessageType[];
      from?: string;
      to?: string;
      cursor?: string;
    }
  ) => {
    const params = new URLSearchParams();
    params.set("limit", String(options?.limit ?? 200));
    params.set("sort", options?.sort ?? "desc");
    params.set("include_meta", "true");
    options?.types?.forEach((type) => params.append("type", type));
    if (options?.from) {
      params.set("from", options.from);
    }
    if (options?.to) {
      params.set("to", options.to);
    }
    if (options?.cursor) {
      params.set("cursor", options.cursor);
    }
    return request<TaskEventsResponse>(`/api/tasks/${taskId}/events?${params.toString()}`);
  },
  getTaskAttempts: (taskId: string) => request<TaskAttemptsResponse>(`/api/tasks/${taskId}/attempts`),
  getTaskConsensus: (taskId: string) => request<TaskConsensusResponse>(`/api/tasks/${taskId}/consensus`),
  simulateTask: (taskId: string, mode: "success" | "failure") =>
    request<Task>(`/api/tasks/${taskId}/simulate`, {
      method: "POST",
      body: JSON.stringify({ mode })
    }),
  retryTask: (taskId: string, reason?: string) =>
    request<Task>(`/api/tasks/${taskId}/retry`, {
      method: "POST",
      body: JSON.stringify({ requeue: true, reason })
    }),
  previewExecuteTask: (taskId: string, payload: TaskExecutionRequest) =>
    request<TaskExecutionPreviewResponse>(`/api/tasks/${taskId}/execute/preview`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  executeTask: (taskId: string, payload: TaskExecutionRequest) =>
    request<Task>(`/api/tasks/${taskId}/execute`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportTaskResult: async (taskId: string, format: TaskResultExportFormat) => {
    const headers = new Headers();
    applyStoredAuthHeaders(headers);
    const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/result/export?format=${format}`, {
      method: "GET",
      headers,
      cache: "no-store"
    });
    if (!response.ok) {
      throw await buildHttpError(response);
    }
    const contentDisposition = response.headers.get("content-disposition") ?? "";
    const matched = /filename="?([^";]+)"?/i.exec(contentDisposition);
    const filename = matched?.[1] ?? `${taskId}.${format}`;
    return {
      filename,
      blob: await response.blob()
    };
  },
  claimTask: (taskId: string, agentId: string, note?: string) =>
    request<Task>(`/api/tasks/${taskId}/claim`, {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, note })
    }),
  handoffTask: (taskId: string, fromAgentId: string, toAgentId: string, reason?: string) =>
    request<Task>(`/api/tasks/${taskId}/handoff`, {
      method: "POST",
      body: JSON.stringify({
        from_agent_id: fromAgentId,
        to_agent_id: toAgentId,
        reason
      })
    }),
};

