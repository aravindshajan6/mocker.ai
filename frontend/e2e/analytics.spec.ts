import { expect, test } from "@playwright/test";
import { ADMIN_STORAGE_STATE, STORAGE_STATE } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { try { localStorage.setItem("mocker:tour-done", "1"); } catch { /* private mode */ } });
});

test.describe("usage analytics", () => {
  test.use({ storageState: STORAGE_STATE });

  test("the app sends a heartbeat while it is on screen and in use", async ({ page }) => {
    // A fake clock lets us skip the 30-second wait instead of sleeping through it.
    await page.clock.install();
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Daily challenge" }).first()).toBeVisible();
    const beat = page.waitForRequest((r) => r.url().endsWith("/api/me/heartbeat") && r.method() === "POST");
    await page.clock.fastForward("00:31");
    const res = await (await beat).response();
    expect(res?.status()).toBe(204);
  });

  test("learners are refused the analytics page", async ({ page }) => {
    await page.goto("/admin/analytics");
    await expect(page.getByText("Administrators only")).toBeVisible();
  });
});

test.describe("admin analytics dashboard", () => {
  test.use({ storageState: ADMIN_STORAGE_STATE });

  test("renders every section and switches range", async ({ page }) => {
    await page.goto("/admin/analytics");
    await expect(page.getByRole("heading", { name: "Analytics", level: 1 })).toBeVisible();
    for (const title of ["Active learners", "Engagement", "Screen time", "Answers", "Accuracy over time",
      "Accuracy by subject", "Practice by subject", "How learners practise", "When learners study",
      "By weekday", "Retention by sign-up week", "Current streaks", "Mock exam scores",
      "Most active learners", "Hardest questions"]) {
      await expect(page.getByRole("heading", { name: title, exact: true, level: 2 })).toBeVisible();
    }

    const seven = page.getByRole("radio", { name: "7 days" });
    await seven.click();
    await expect(seven).toHaveAttribute("aria-checked", "true");
    await expect(page.getByText(/vs prior 7d/).first()).toBeVisible();
  });

  test("charts are keyboard-readable, and nav lights only Analytics", async ({ page }) => {
    await page.goto("/admin/analytics");
    const chart = page.getByRole("group", { name: /Active learners per day/ });
    await chart.focus();
    await page.keyboard.press("End");
    await expect(chart.locator("[aria-live]")).toHaveText(/active/);

    // Most-specific match: /admin/analytics must not also light "Admin".
    const nav = page.locator("aside");
    await expect(nav.getByRole("link", { name: "Analytics" })).toHaveClass(/text-primary/);
    await expect(nav.getByRole("link", { name: "Admin", exact: true })).not.toHaveClass(/text-primary/);
  });

  test("the accounts tab links to the dashboard", async ({ page }) => {
    await page.goto("/admin");
    await page.getByRole("button", { name: /Accounts/ }).click();
    await page.getByRole("link", { name: /Analytics dashboard/ }).click();
    await expect(page).toHaveURL(/\/admin\/analytics$/);
  });
});
