import { BusMessage } from "@/lib/api/types";

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";

export function subscribeTaskEvents(
  taskId: string,
  onMessage: (event: BusMessage) => void,
  onError?: (error: Event) => void,
  onClose?: () => void
): () => void {
  const socket = new WebSocket(`${WS_BASE_URL}/ws/tasks/${taskId}`);
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

