import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard smoke flow: create task and simulate success", async ({ page, request }) => {
  const health = await request.get(`${getBackendBaseUrl()}/health`);
  expect(health.ok()).toBeTruthy();

  const uniqueObjective = `E2E objective ${Date.now()}`;

  await page.goto("/tasks");

  await page.getByTestId("task-objective-input").fill(uniqueObjective);
  await page.getByTestId("task-create-button").click();

  await expect(page).toHaveURL(/\/tasks\//);

  await expect(page.getByRole("heading", { name: uniqueObjective })).toBeVisible();
  await expect(page.getByTestId("task-status-line")).toContainText("状态:");

  await page.getByTestId("task-simulate-success-button").click();

  await expect(page.getByTestId("task-status-line")).toContainText("状态: completed", {
    timeout: 10000
  });
});

