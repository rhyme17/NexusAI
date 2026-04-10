import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard retry flow: fail then retry then complete", async ({ page, request }) => {
  const health = await request.get(`${getBackendBaseUrl()}/health`);
  expect(health.ok()).toBeTruthy();

  const uniqueObjective = `E2E retry objective ${Date.now()}`;

  await page.goto("/tasks");

  await page.getByTestId("task-objective-input").fill(uniqueObjective);
  await page.getByTestId("task-create-button").click();

  await expect(page).toHaveURL(/\/tasks\//);

  await expect(page.getByRole("heading", { name: uniqueObjective })).toBeVisible();

  await page.getByTestId("task-simulate-failure-button").click();
  await expect(page.getByTestId("task-status-line")).toContainText("状态: failed", {
    timeout: 10000
  });

  const retryButton = page.getByTestId("task-retry-button");
  await expect(retryButton).toBeEnabled();
  await retryButton.click();

  await expect(page.getByTestId("task-status-line")).toContainText("状态: in_progress", {
    timeout: 10000
  });

  await page.getByTestId("task-simulate-success-button").click();
  await expect(page.getByTestId("task-status-line")).toContainText("状态: completed", {
    timeout: 10000
  });
});

