import { expect, test } from "@playwright/test";

test.describe("landing page", () => {
  test("a signed-out visitor at the root is sent to the marketing page", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/welcome/);
  });

  test("a signed-out deep link still goes to sign-in, not marketing", async ({ page }) => {
    await page.goto("/progress");
    await expect(page).toHaveURL(/\/login/);
  });

  test("renders every section and quotes live question counts", async ({ page }) => {
    await page.goto("/welcome");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("One more question");

    // The three counters are fed by /api/public/stats. NumberFlow renders each digit as an
    // animated reel of spans, so assert the endpoint's number and the tiles' presence separately
    // rather than trying to scrape a value out of that DOM.
    const stats = await (await page.request.get("/api/public/stats")).json();
    expect(stats.questions).toBeGreaterThan(1000);
    for (const label of ["Questions", "Subjects", "From real papers"]) {
      await expect(page.getByRole("term").filter({ hasText: label })).toBeVisible();
    }

    for (const heading of [
      "Everything you need, nothing you don't",
      "A rhythm that carries you to exam day",
      "Know exactly where you stand",
      "Rehearse the exam before the exam",
      "Questions you can actually trust",
      "And the rest of the toolkit",
      "Your preparation starts today",
    ]) {
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    }
    await expect(page.getByRole("link", { name: /Kerala Public Service Commission/ })).toBeVisible();
  });

  test("both calls to action lead to sign-in", async ({ page }) => {
    await page.goto("/welcome");
    await page.getByRole("link", { name: /Start practising/ }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/welcome");
    await page.getByRole("link", { name: /Sign in and begin/ }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
