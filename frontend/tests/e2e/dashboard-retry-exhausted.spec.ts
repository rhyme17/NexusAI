import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard retry exhausted flow: failed task cannot be retried beyond limit", async ({ page, request }) => {
  const backendBaseUrl = getBackendBaseUrl();
  const uniqueObjective = `E2E retry exhausted ${Date.now()}`;

  const created = await request.post(`${backendBaseUrl}/api/tasks`, {
    data: {
      objective: uniqueObjective,
      priority: "high",
      metadata: {
        max_retries: 0
      }
    }
  });
  expect(created.ok()).toBeTruthy();

  const createdTask = (await created.json()) as { task_id: string };

  await page.goto(`/tasks/${createdTask.task_id}`);

  await page.getByTestId("task-simulate-failure-button").click();
  await expect(page.getByTestId("task-status-line")).toContainText("状态: failed", {
    timeout: 10000
  });

  await page.getByTestId("task-retry-button").click();

  await expect(page.getByText("已达到重试上限。请先提高 max_retries 或排查失败原因后再重试。")).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId("task-status-line")).toContainText("状态: failed");
});

