import { defineConfig, devices } from "@playwright/test";

const frontendBaseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: frontendBaseUrl,
    trace: "on-first-retry"
  },
  webServer: {
    command: "npm run dev",
    url: frontendBaseUrl,
    reuseExistingServer: true,
    timeout: 120000
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});

