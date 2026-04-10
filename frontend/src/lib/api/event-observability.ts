import type { BusMessage } from "@/lib/api/types";

function asDisplayValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function getEventField(event: BusMessage | undefined, keys: string[]): string {
  if (!event) {
    return "-";
  }
  for (const key of keys) {
    const value = event.payload[key];
    if (value !== undefined && value !== null && value !== "") {
      return asDisplayValue(value);
    }
  }
  return "-";
}

export function getDecisionActor(event: BusMessage | undefined): string {
  return getEventField(event, ["decided_by", "strategy"]);
}

export function getDecisionReason(event: BusMessage | undefined): string {
  return getEventField(event, ["reason", "selection_basis", "detail"]);
}

export function getFailureCode(event: BusMessage | undefined): string {
  return getEventField(event, ["error_code", "code"]);
}

export function getFailureMessage(event: BusMessage | undefined): string {
  return getEventField(event, ["error_message", "user_message", "detail"]);
}

export function sortEventsByTimestampDesc(events: BusMessage[]): BusMessage[] {
  return [...events].sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime());
}

