import { expect, test } from "@playwright/test";
import { STORAGE_STATE } from "./helpers";

test.use({ storageState: STORAGE_STATE });

// Named app-tour so it sorts before app.spec: the tour only greets an account that has
// answered nothing, and app.spec's quiz flow spends that innocence.
test("Kunju's tour greets a new account, walks through, and starts the daily challenge", async ({ page }) => {
  await page.goto("/");
  const dialog = page.getByRole("dialog", { name: "Welcome tour" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Hi, I'm Kunju!");
  await dialog.getByRole("button", { name: "Show me around" }).click();

  for (const excerpt of [/daily challenge/i, /costs you marks/i, /real exam/i, /improve/i]) {
    await expect(dialog).toContainText(excerpt);
    await dialog.getByRole("button", { name: /^Next$|Start today/ }).click();
  }
  await expect(page).toHaveURL(/\/daily/);

  // Completing it must persist: back on Home, no tour.
  await page.goto("/");
  await expect(dialog).not.toBeVisible();
});
