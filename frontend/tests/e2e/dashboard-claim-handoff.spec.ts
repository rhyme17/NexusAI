import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard coordination flow: claim then handoff updates event timeline", async ({ page, request }) => {
  const health = await request.get(`${getBackendBaseUrl()}/health`);
  expect(health.ok()).toBeTruthy();

  const uniqueObjective = `E2E coordination ${Date.now()}`;

  await page.goto("/tasks");

  await page.getByTestId("task-objective-input").fill(uniqueObjective);
  await page.getByTestId("task-create-button").click();

  await expect(page).toHaveURL(/\/tasks\//);
  await expect(page.getByRole("heading", { name: uniqueObjective })).toBeVisible();

  await page.getByTestId("task-claim-agent-select").selectOption("agent_planner");
  await page.getByTestId("task-claim-button").click();

  await page.getByTestId("task-handoff-target-select").selectOption("agent_research");
  await page.getByTestId("task-handoff-button").click();

  const eventStream = page.getByTestId("event-stream-list");
  await expect(eventStream.getByText("TaskClaim")).toBeVisible({ timeout: 10000 });
  await expect(eventStream.getByText("TaskHandoff")).toBeVisible({ timeout: 10000 });
});

