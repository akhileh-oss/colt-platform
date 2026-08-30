import { expect, test } from "@playwright/test";

/**
 * The Milestone 03 acceptance bar: the app shell renders, navigates, and reflects real API
 * data — not synthetic fixtures (CLAUDE.md §68, §45.3).
 */

test("root redirects to the dashboard", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("dashboard renders the shell, nav, and live system health", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();

  // Real data from the /live and /ready probes built in Milestone 02 — the API is running
  // via the Playwright webServer, so this is not a mock. Scoped to the sidebar: the health
  // badge also renders in the mobile header, hidden by CSS but still present in the DOM.
  const sidebar = page.getByRole("complementary");
  await expect(sidebar.getByText("All systems healthy")).toBeVisible({ timeout: 10_000 });

  await expect(page.getByText("API process alive")).toBeVisible();
  await expect(page.getByText("API ready to accept work")).toBeVisible();
});

test("every nav item routes to its feature area", async ({ page }) => {
  await page.goto("/dashboard");

  // Nav label vs. page heading intentionally differ for Agents: the nav stays a concise
  // one-word label, the page heading uses the exact term from CLAUDE.md §43.1.
  const items: Array<[navLabel: string, path: string, heading: string]> = [
    ["Leads", "/leads", "Leads"],
    ["Companies", "/companies", "Companies"],
    ["Campaigns", "/campaigns", "Campaigns"],
    ["Conversations", "/conversations", "Conversations"],
    ["Opportunities", "/opportunities", "Opportunities"],
    ["Agents", "/agents", "Agent control center"],
    ["Settings", "/settings", "Settings"],
  ];

  for (const [navLabel, path, heading] of items) {
    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: navLabel })
      .click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
    await expect(page.getByRole("heading", { name: "Not built yet" })).toBeVisible();
  }
});

test("an unknown route shows the not-found page with a way back", async ({ page }) => {
  await page.goto("/this-route-does-not-exist");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();

  await page.getByRole("link", { name: "Back to dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("keyboard navigation reaches the primary nav and a skip link is available", async ({
  page,
}) => {
  await page.goto("/dashboard");

  // CLAUDE.md §78: keyboard navigation and a visible focus state.
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to content" });
  await expect(skipLink).toBeFocused();

  await page.keyboard.press("Tab");
  const firstNavLink = page.getByRole("navigation", { name: "Primary" }).getByRole("link").first();
  await expect(firstNavLink).toBeFocused();
});

test("has no client-side console errors on the primary screens", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  for (const path of ["/dashboard", "/leads", "/agents"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
  }

  expect(errors).toEqual([]);
});
