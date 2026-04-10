"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { CreateTaskPayload, Task } from "@/lib/api/types";

const ENABLE_NAV_CACHE = process.env.NODE_ENV !== "test";
const TASKS_CACHE_TTL_MS = 10000;

let tasksCache: { data: Task[]; cachedAt: number } | null = null;
let tasksInFlight: Promise<Task[]> | null = null;

async function loadTasksWithDedupe(force = false): Promise<Task[]> {
  if (!ENABLE_NAV_CACHE) {
    return apiClient.listTasks();
  }
  const now = Date.now();
  if (!force && tasksCache && now - tasksCache.cachedAt < TASKS_CACHE_TTL_MS) {
    return tasksCache.data;
  }
  if (tasksInFlight) {
    return tasksInFlight;
  }
  tasksInFlight = apiClient
    .listTasks()
    .then((nextTasks) => {
      tasksCache = { data: nextTasks, cachedAt: Date.now() };
      return nextTasks;
    })
    .finally(() => {
      tasksInFlight = null;
    });
  return tasksInFlight;
}

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextTasks = await loadTasksWithDedupe(true);
      setTasks(nextTasks);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch tasks"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createTask = useCallback(async (payload: CreateTaskPayload) => {
    const created = await apiClient.createTask(payload);
    if (ENABLE_NAV_CACHE && tasksCache) {
      tasksCache = { data: [created, ...tasksCache.data], cachedAt: Date.now() };
    }
    setTasks((prev) => [created, ...prev]);
    return created;
  }, []);

  const upsertTask = useCallback((task: Task) => {
    setTasks((prev) => {
      const index = prev.findIndex((item) => item.task_id === task.task_id);
      if (index < 0) {
        if (ENABLE_NAV_CACHE && tasksCache) {
          tasksCache = { data: [task, ...tasksCache.data], cachedAt: Date.now() };
        }
        return [task, ...prev];
      }
      const cloned = [...prev];
      cloned[index] = task;
      if (ENABLE_NAV_CACHE && tasksCache) {
        const cacheIndex = tasksCache.data.findIndex((item) => item.task_id === task.task_id);
        if (cacheIndex < 0) {
          tasksCache = { data: [task, ...tasksCache.data], cachedAt: Date.now() };
        } else {
          const cacheCloned = [...tasksCache.data];
          cacheCloned[cacheIndex] = task;
          tasksCache = { data: cacheCloned, cachedAt: Date.now() };
        }
      }
      return cloned;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void loadTasksWithDedupe(false)
      .then((nextTasks) => {
        if (!cancelled) {
          setTasks(nextTasks);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error("Failed to fetch tasks"));
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    tasks,
    isLoading,
    error,
    refresh,
    createTask,
    upsertTask
  };
}

