import { adminFetch, apiLogin, ADMIN_EMAIL, ADMIN_PASSWORD, TEST_EMAIL } from "./helpers";

export default async function globalTeardown() {
  const admin = await apiLogin(ADMIN_EMAIL, ADMIN_PASSWORD);
  const users = await (await adminFetch(admin, "/api/admin/users")).json();
  const testUser = users.find((u: { email: string }) => u.email === TEST_EMAIL);
  if (testUser) await adminFetch(admin, `/api/admin/users/${testUser.id}`, { method: "DELETE" });
}
