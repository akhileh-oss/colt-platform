import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests (CLAUDE.md §45.3). Specs live under `tests/e2e/`, per the repository layout
 * fixed in `CLAUDE.md` §4 — not colocated with the app, since e2e exercises the full stack
 * (API + web), not `apps/web` alone.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    // This sandbox pins a Chromium build the installed @playwright/test version doesn't
    // recognise by revision; point at the pre-installed browser directly rather than
    // downloading one (see the environment's own guidance on this).
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH ?? "/opt/pw-browsers/chromium",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run python -m colt_api",
      cwd: ".",
      url: "http://localhost:8000/live",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: { APP_ENV: "local" },
    },
    {
      // Builds first: `next start` requires a production build, and this must be
      // self-contained rather than assuming a prior `make build` happened first.
      command: "pnpm --filter @colt/web build && pnpm --filter @colt/web start",
      cwd: ".",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000" },
    },
  ],
});
