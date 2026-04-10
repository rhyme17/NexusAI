"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { BusMessage, MessageType } from "@/lib/api/types";
import { subscribeTaskEvents } from "@/lib/ws/task-events";

interface TaskEventFilters {
  types: MessageType[];
  from: string;
  to: string;
}

const BASE_RETRY_DELAY_MS = 1500;
const MAX_RETRY_DELAY_MS = 12000;

function getReconnectDelayMs(retryAttempt: number) {
  const exponential = BASE_RETRY_DELAY_MS * 2 ** Math.min(retryAttempt, 3);
  const bounded = Math.min(exponential, MAX_RETRY_DELAY_MS);
  const jitter = Math.floor(Math.random() * 400);
  return bounded + jitter;
}

export function useTaskEvents(taskId: string | null, filters: TaskEventFilters) {
  const [events, setEvents] = useState<BusMessage[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [connectionState, setConnectionState] = useState<"idle" | "connecting" | "connected" | "reconnecting">("idle");
  const [retryTick, setRetryTick] = useState(0);
  const retryTimerRef = useRef<number | null>(null);
  const filtersRef = useRef<TaskEventFilters>(filters);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  const parseIso = (input: string) => {
    const parsed = new Date(input);
    if (Number.isNaN(parsed.getTime())) {
      return undefined;
    }
    return parsed.toISOString();
  };

  const fromIso = filters.from ? parseIso(filters.from) : undefined;
  const toIso = filters.to ? parseIso(filters.to) : undefined;

  const eventPassesFilters = useCallback((event: BusMessage) => {
      const currentFilters = filtersRef.current;
      if (currentFilters.types.length > 0 && !currentFilters.types.includes(event.type)) {
        return false;
      }
      const eventTime = new Date(event.timestamp).getTime();
      if (currentFilters.from) {
        const fromTime = new Date(currentFilters.from).getTime();
        if (!Number.isNaN(fromTime) && eventTime < fromTime) {
          return false;
        }
      }
      if (currentFilters.to) {
        const toTime = new Date(currentFilters.to).getTime();
        if (!Number.isNaN(toTime) && eventTime > toTime) {
          return false;
        }
      }
      return true;
    }, []);

  const refresh = useCallback(async () => {
    if (!taskId) {
      setEvents([]);
      return;
    }

    try {
      const merged: BusMessage[] = [];
      let cursor: string | undefined = undefined;
      for (let page = 0; page < 3; page += 1) {
        const snapshot = await apiClient.listTaskEventsMeta(taskId, {
          types: filters.types,
          from: fromIso,
          to: toIso,
          limit: 150,
          sort: "desc",
          cursor
        });
        merged.push(...snapshot.items);
        if (!snapshot.has_more || !snapshot.next_cursor) {
          break;
        }
        cursor = snapshot.next_cursor;
      }
      setEvents(merged.slice(0, 400));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch events"));
    }
  }, [taskId, filters.types, fromIso, toIso]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!taskId) {
      setConnectionState("idle");
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      return;
    }

    let cancelled = false;
    setConnectionState(retryTick === 0 ? "connecting" : "reconnecting");

    const unsubscribe = subscribeTaskEvents(
      taskId,
      (nextEvent) => {
        if (eventPassesFilters(nextEvent)) {
          setEvents((prev) => [nextEvent, ...prev].slice(0, 200));
        }
        setError(null);
        setRetryTick(0);
        setConnectionState("connected");
      },
      () => {
        setError(new Error("WS_CONNECTION_FAILED"));
      },
      () => {
        if (cancelled) {
          return;
        }
        setConnectionState("reconnecting");
        setError(new Error("WS_CONNECTION_INTERRUPTED"));
        const delayMs = getReconnectDelayMs(retryTick + 1);
        retryTimerRef.current = window.setTimeout(() => {
          if (!cancelled) {
            setRetryTick((prev) => prev + 1);
          }
        }, delayMs);
      }
    );

    return () => {
      cancelled = true;
      unsubscribe();
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, [taskId, retryTick, eventPassesFilters]);

  const insights = useMemo(() => {
    const latestClaim = events.find((event) => event.type === "TaskClaim");
    const handoffs = events.filter((event) => event.type === "TaskHandoff");
    const latestDecision = events.find((event) => event.type === "Decision");
    const latestFailure = events.find((event) => event.type === "TaskFailed");

    return {
      latestClaim,
      handoffCount: handoffs.length,
      latestDecision,
      latestFailure
    };
  }, [events]);

  return {
    events,
    error,
    refresh,
    connectionState,
    insights
  };
}

