import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard tasks flow: conflict filter only shows conflict tasks", async ({ page, request }) => {
  const backendBaseUrl = getBackendBaseUrl();

  const plainObjective = `E2E plain ${Date.now()}`;
  const plainCreated = await request.post(`${backendBaseUrl}/api/tasks`, {
    data: {
      objective: plainObjective,
      priority: "medium"
    }
  });
  expect(plainCreated.ok()).toBeTruthy();
  const plainTask = (await plainCreated.json()) as { task_id: string };

  const conflictObjective = `E2E conflict ${Date.now()}`;
  const conflictCreated = await request.post(`${backendBaseUrl}/api/tasks`, {
    data: {
      objective: conflictObjective,
      priority: "high"
    }
  });
  expect(conflictCreated.ok()).toBeTruthy();
  const conflictTask = (await conflictCreated.json()) as { task_id: string };

  const proposalOne = await request.patch(`${backendBaseUrl}/api/tasks/${conflictTask.task_id}/status`, {
    data: {
      status: "in_progress",
      progress: 55,
      agent_id: "agent_planner",
      confidence: 0.7,
      result: {
        summary: "conflict plan A",
        detail: "first view"
      }
    }
  });
  expect(proposalOne.ok()).toBeTruthy();

  const proposalTwo = await request.patch(`${backendBaseUrl}/api/tasks/${conflictTask.task_id}/status`, {
    data: {
      status: "completed",
      progress: 100,
      agent_id: "agent_research",
      confidence: 0.9,
      result: {
        summary: "conflict plan B",
        detail: "second view"
      }
    }
  });
  expect(proposalTwo.ok()).toBeTruthy();
  const updatedConflictTask = (await proposalTwo.json()) as { consensus?: { conflict_detected?: boolean } };
  expect(updatedConflictTask.consensus?.conflict_detected).toBeTruthy();

  await page.goto("/tasks");

  await page.getByTestId("task-only-conflicts-toggle").check();

  await expect(page.getByTestId(`task-item-${conflictTask.task_id}`)).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId(`task-item-${plainTask.task_id}`)).toHaveCount(0);
});

