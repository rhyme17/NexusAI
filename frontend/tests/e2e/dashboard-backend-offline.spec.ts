import { expect, test } from "@playwright/test";

import { getBackendBaseUrl } from "./env";

test("dashboard resilience flow: tasks page shows readable message when backend is offline", async ({ page }) => {
  const backendBaseUrl = getBackendBaseUrl();

  await page.route(`${backendBaseUrl}/api/tasks*`, async (route) => {
    await route.abort("failed");
  });

  await page.goto("/tasks");

  await expect(page.getByText("无法加载任务列表。请刷新页面，或确认后端服务已启动。")).toBeVisible({ timeout: 10000 });
});

