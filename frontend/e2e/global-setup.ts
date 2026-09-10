import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { adminFetch, apiLogin, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_STORAGE_STATE, BASE, STORAGE_STATE, TEST_EMAIL, TEST_PASSWORD } from "./helpers";

async function deleteTestUser(admin: string) {
  const users = await (await adminFetch(admin, "/api/admin/users")).json();
  const stale = users.find((u: { email: string }) => u.email === TEST_EMAIL);
  if (stale) await adminFetch(admin, `/api/admin/users/${stale.id}`, { method: "DELETE" });
}

export default async function globalSetup() {
  // Login is rate-limited (8/minute); the dev stack runs with TESTING_HOOKS=true so a reset is
  // available, exactly as the backend suite uses it. Ignore failures — prod-like stacks 404 here.
  await fetch(`${BASE}/api/testing/reset-rate-limits`, { method: "POST" }).catch(() => {});
  const admin = await apiLogin(ADMIN_EMAIL, ADMIN_PASSWORD);
  await deleteTestUser(admin); // a crashed previous run may have left one behind
  const created = await adminFetch(admin, "/api/admin/users", {
    method: "POST",
    body: JSON.stringify({ name: "UI Test", email: TEST_EMAIL, password: TEST_PASSWORD }),
  });
  if (!created.ok) throw new Error(`could not provision ${TEST_EMAIL}: ${created.status} ${await created.text()}`);

  // Sign the test user in once and persist the cookie as Playwright storage state. The admin
  // session from above is saved too, so admin-page tests need no login of their own.
  const token = await apiLogin(TEST_EMAIL, TEST_PASSWORD);
  const { hostname } = new URL(BASE);
  const state = (value: string) => JSON.stringify({
    cookies: [{
      name: "mocker_token", value, domain: hostname, path: "/",
      expires: Math.floor(Date.now() / 1000) + 86400, httpOnly: true, secure: false, sameSite: "Lax",
    }],
    origins: [],
  });
  mkdirSync(dirname(STORAGE_STATE), { recursive: true });
  writeFileSync(STORAGE_STATE, state(token));
  writeFileSync(ADMIN_STORAGE_STATE, state(admin));
}
