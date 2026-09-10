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
});

test.describe("admin analytics", () => {
  test.use({ storageState: ADMIN_STORAGE_STATE });

  test("the accounts tab shows usage, charts and the study-hours grid", async ({ page }) => {
    await page.goto("/admin");
    await page.getByRole("button", { name: /Accounts/ }).click();
    await expect(page.getByText("Usage", { exact: true })).toBeVisible();
    await expect(page.getByText("Active today")).toBeVisible();
    await expect(page.getByRole("group", { name: /Active learners per day/ })).toBeVisible();
    await expect(page.getByRole("group", { name: /Screen time per day/ })).toBeVisible();
    await expect(page.getByRole("group", { name: /Study hours grid/ })).toBeVisible();

    // Keyboard parity with hover: focusing a chart and scrubbing announces a value.
    const chart = page.getByRole("group", { name: /Active learners per day/ });
    await chart.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(chart.locator("[aria-live]")).toHaveText(/: \d+ active$/);
  });
});
