import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AUTH_TOKEN_COOKIE_NAME,
  apiClient,
  clearStoredAuthToken,
  clearStoredBackendApiKey,
  setStoredAuthToken,
  setStoredBackendApiKey
} from "./client";

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      "Content-Type": "application/json"
    },
    ...init
  });
}

describe("apiClient", () => {
  const fetchMock = vi.fn();

  afterEach(() => {
    clearStoredAuthToken();
    clearStoredBackendApiKey();
    vi.unstubAllGlobals();
  });

  it("builds task events query params correctly", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse([]));

    await apiClient.listTaskEvents("task_123", {
      limit: 20,
      sort: "desc",
      types: ["TaskFailed", "Decision"],
      from: "2026-04-05T10:00:00.000Z",
      to: "2026-04-05T12:00:00.000Z"
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    const parsedUrl = new URL(url);

    expect(parsedUrl.pathname).toBe("/api/tasks/task_123/events");
    expect(parsedUrl.searchParams.get("limit")).toBe("20");
    expect(parsedUrl.searchParams.get("sort")).toBe("desc");
    expect(parsedUrl.searchParams.getAll("type")).toEqual(["TaskFailed", "Decision"]);
    expect(parsedUrl.searchParams.get("from")).toBe("2026-04-05T10:00:00.000Z");
    expect(parsedUrl.searchParams.get("to")).toBe("2026-04-05T12:00:00.000Z");
  });

  it("builds task events meta query params correctly", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse({
        total_count: 1,
        offset: 0,
        limit: 200,
        sort: "desc",
        has_more: false,
        next_cursor: null,
        items: []
      })
    );

    await apiClient.listTaskEventsMeta("task_meta", {
      limit: 150,
      sort: "desc",
      cursor: "30",
      types: ["TaskResult"]
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    const parsedUrl = new URL(url);
    expect(parsedUrl.pathname).toBe("/api/tasks/task_meta/events");
    expect(parsedUrl.searchParams.get("include_meta")).toBe("true");
    expect(parsedUrl.searchParams.get("cursor")).toBe("30");
    expect(parsedUrl.searchParams.get("limit")).toBe("150");
    expect(parsedUrl.searchParams.getAll("type")).toEqual(["TaskResult"]);
  });

  it("posts task creation payload as JSON", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ task_id: "task_1" }));

    await apiClient.createTask({
      objective: "Create dashboard baseline",
      priority: "high"
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ objective: "Create dashboard baseline", priority: "high" }));
  });

  it("posts agent registration payload as JSON", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ agent_id: "agent_1" }));

    await apiClient.registerAgent({
      name: "planner-2",
      role: "planner",
      skills: ["plan", "workflow"]
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(url).pathname).toBe("/api/agents");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "planner-2", role: "planner", skills: ["plan", "workflow"] }));
  });

  it("fetches backend health from the system endpoint", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));

    const result = await apiClient.getHealth();

    expect(result.status).toBe("ok");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/health", expect.objectContaining({ cache: "no-store" }));
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("injects stored backend api key into protected requests", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse([]));
    setStoredBackendApiKey("internal-ops-key");

    await apiClient.listAgents();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("X-API-Key")).toBe("internal-ops-key");
  });

  it("injects bearer token into requests when user is authenticated", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse([]));
    setStoredAuthToken("bearer-token-1");

    await apiClient.listTasks();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer bearer-token-1");
  });

  it("dedupes concurrent current-user requests for the same auth token", async () => {
    vi.stubGlobal("fetch", fetchMock);
    setStoredAuthToken("bearer-token-dedupe");
    fetchMock.mockResolvedValue(jsonResponse({ user_id: "u_1", username: "tester", role: "viewer", is_active: true }));

    await Promise.all([apiClient.getCurrentUser(), apiClient.getCurrentUser()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer bearer-token-dedupe");
  });

  it("syncs auth token to cookie and clears it on logout", () => {
    setStoredAuthToken("token-cookie-abc");
    expect(window.localStorage.getItem("nexusai.auth_token")).toBe("token-cookie-abc");
    expect(document.cookie).toContain(`${AUTH_TOKEN_COOKIE_NAME}=token-cookie-abc`);

    clearStoredAuthToken();
    expect(window.localStorage.getItem("nexusai.auth_token")).toBeNull();
    expect(document.cookie).not.toContain(`${AUTH_TOKEN_COOKIE_NAME}=token-cookie-abc`);
  });

  it("stores and clears backend api key locally", () => {
    expect(setStoredBackendApiKey("  ops-key  ")).toBe("ops-key");
    expect(window.localStorage.getItem("nexusai.backend_api_key")).toBe("ops-key");

    clearStoredBackendApiKey();

    expect(window.localStorage.getItem("nexusai.backend_api_key")).toBeNull();
  });

  it("builds agent filter query params correctly", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse([]));

    await apiClient.listAgents({ skill: "review", status: "online" });

    const [url] = fetchMock.mock.calls[0] as [string];
    const parsed = new URL(url);
    expect(parsed.pathname).toBe("/api/agents");
    expect(parsed.searchParams.get("skill")).toBe("review");
    expect(parsed.searchParams.get("status")).toBe("online");
  });

  it("patches agent status payload as JSON", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ agent_id: "agent_1", status: "busy" }));

    await apiClient.updateAgentStatus("agent_1", "busy");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(url).pathname).toBe("/api/agents/agent_1/status");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ status: "busy" }));
  });

  it("builds debug clear storage query params correctly", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ status: "cleared" }));

    await apiClient.clearServerData({
      keepDefaultAgents: true,
      clearEventsOnly: false,
      restoreSeed: true
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url);
    expect(parsed.pathname).toBe("/api/debug/storage/clear");
    expect(parsed.searchParams.get("keep_default_agents")).toBe("true");
    expect(parsed.searchParams.get("clear_events_only")).toBe("false");
    expect(parsed.searchParams.get("restore_seed")).toBe("true");
    expect(init.method).toBe("POST");
  });

  it("calls delete-own-account endpoint with DELETE", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ status: "deleted", deleted_tasks: 2 }));

    await apiClient.deleteOwnAccount();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(url).pathname).toBe("/api/auth/me");
    expect(init.method).toBe("DELETE");
  });

  it("extracts detail and user_message from JSON error responses", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse(
        { detail: "Retry limit reached", user_message: "已达到重试上限。" },
        { status: 409 }
      )
    );

    await expect(apiClient.retryTask("task_1")).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "http",
      status: 409,
      detail: "Retry limit reached",
      userMessage: "已达到重试上限。"
    });
  });

  it("wraps network failures as ApiClientError", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiClient.listAgents()).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "network",
      detail: "Failed to fetch"
    });
  });
});

