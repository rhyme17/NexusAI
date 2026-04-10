"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { Task } from "@/lib/api/types";

export function useTaskRecord(taskId: string) {
  const [task, setTask] = useState<Task | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextTask = await apiClient.getTask(taskId);
      setTask(nextTask);
    } catch (err) {
      setTask(null);
      setError(err instanceof Error ? err : new Error("Failed to fetch task"));
    } finally {
      setIsLoading(false);
    }
  }, [taskId]);

  const updateTask = useCallback((nextTask: Task) => {
    setTask(nextTask);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    task,
    isLoading,
    error,
    refresh,
    updateTask
  };
}

