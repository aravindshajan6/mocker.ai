import { expect, test } from "@playwright/test";
import { TEST_EMAIL, TEST_PASSWORD } from "./helpers";

test.describe("authentication", () => {
  test("redirects a signed-out visitor to the login page", async ({ page }) => {
    await page.goto("/daily");
    await expect(page).toHaveURL(/\/login/);
  });

  test("rejects a wrong password with a visible error", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill(TEST_EMAIL);
    await page.getByPlaceholder("Your password").fill("definitely-wrong");
    await page.locator("form button.btn-primary").click();
    // Not getByRole("alert"): Next's route announcer is also role=alert, so target the text.
    await expect(page.getByText("Incorrect email or password")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("signs in through the form and lands in the app", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill(TEST_EMAIL);
    await page.getByPlaceholder("Your password").fill(TEST_PASSWORD);
    await page.locator("form button.btn-primary").click();
    await expect(page.getByRole("link", { name: "Daily challenge" })).toBeVisible();
  });
});
