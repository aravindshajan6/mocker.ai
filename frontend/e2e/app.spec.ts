import { expect, test } from "@playwright/test";
import { STORAGE_STATE } from "./helpers";

test.use({ storageState: STORAGE_STATE });

test.describe("signed-in flows", () => {
  test("topics page lists the question banks", async ({ page }) => {
    await page.goto("/practice");
    await expect(page.getByText("Indian History")).toBeVisible();
    await expect(page.getByText("English", { exact: true })).toBeVisible();
  });

  test("daily challenge page renders", async ({ page }) => {
    await page.goto("/daily");
    await expect(page.getByText(/daily challenge/i).first()).toBeVisible();
  });

  test("reminder time picker keeps the hour select wide and the minute select narrow", async ({ page }) => {
    // Regression: .field's w-full used to make the minute select swallow the row,
    // collapsing the hour select to a bare chevron.
    await page.goto("/settings");
    const toggle = page.getByRole("switch").first();
    await expect(toggle).toBeVisible();
    if ((await toggle.getAttribute("aria-checked")) === "false") await toggle.click();
    const selects = page.locator("select");
    await expect(selects).toHaveCount(2);
    const hour = (await selects.nth(0).boundingBox())!;
    const minute = (await selects.nth(1).boundingBox())!;
    expect(hour.width).toBeGreaterThan(minute.width * 2);
    expect(minute.width).toBeLessThan(200);
  });

  test("completes a 5-question practice quiz and reaches the result page", async ({ page }) => {
    await page.goto("/practice/english");
    await page.getByRole("button", { name: "5", exact: true }).click();
    await expect(page).toHaveURL(/\/quiz\//);
    for (let i = 0; i < 5; i++) {
      await page.locator(".option").first().click();
      await page.locator("button.btn-primary").click();
      // Feedback card: verdict text, explanation, and Kunju popped in beside them.
      await expect(page.locator(".mascot-pop")).toBeVisible();
      await expect(page.getByText("Explain this more")).toBeVisible();
      await page.locator("button.btn-primary").click(); // next / see results
    }
    await expect(page).toHaveURL(/\/result/);
    await expect(page.getByText("Accuracy")).toBeVisible();
  });

  test("signs out back to the login page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
