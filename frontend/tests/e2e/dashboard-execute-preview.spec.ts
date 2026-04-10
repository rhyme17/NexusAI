import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard execute flow: preview execution and run execute", async ({ page, request }) => {
  const health = await request.get(`${getBackendBaseUrl()}/health`);
  expect(health.ok()).toBeTruthy();

  const uniqueObjective = `E2E execute objective ${Date.now()}`;

  await page.goto("/tasks");

  await page.getByTestId("task-objective-input").fill(uniqueObjective);
  await page.getByTestId("task-create-button").click();

  await expect(page).toHaveURL(/\/tasks\//);

  await expect(page.getByRole("heading", { name: uniqueObjective })).toBeVisible();
  await expect(page.getByTestId("task-status-line")).toContainText("状态:");

  await page.getByTestId("task-preview-execution-button").click();

  await expect(page.getByTestId("task-execution-preview-panel")).toBeVisible();
  await expect(page.getByText("执行预览")).toBeVisible();

  await page.getByTestId("task-execute-button").click();

  await expect(page.getByTestId("task-status-line")).toContainText("状态: completed", {
    timeout: 15000
  });
});



