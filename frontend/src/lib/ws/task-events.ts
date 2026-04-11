import { BusMessage } from "@/lib/api/types";
import { getStoredAuthToken, getStoredBackendApiKey } from "@/lib/api/client";

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";

export function subscribeTaskEvents(
  taskId: string,
  onMessage: (event: BusMessage) => void,
  onError?: (error: Event) => void,
  onClose?: () => void
): () => void {
  const params = new URLSearchParams();
  const backendApiKey = getStoredBackendApiKey();
  if (backendApiKey) {
    params.set("api_key", backendApiKey);
  }
  const authToken = getStoredAuthToken();
  if (authToken) {
    params.set("access_token", authToken);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const socket = new WebSocket(`${WS_BASE_URL}/ws/tasks/${encodeURIComponent(taskId)}${suffix}`);
  let closedByClient = false;

  socket.onmessage = (messageEvent) => {
    try {
      const parsed = JSON.parse(messageEvent.data) as BusMessage;
      onMessage(parsed);
    } catch {
      // Ignore malformed messages to keep the baseline UI resilient.
    }
  };

  socket.onerror = (errorEvent) => {
    if (onError) {
      onError(errorEvent);
    }
  };

  socket.onclose = () => {
    if (closedByClient) {
      return;
    }
    if (onClose) {
      onClose();
    }
  };

  return () => {
    closedByClient = true;
    if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
      socket.close();
    }
  };
}

