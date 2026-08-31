export const BASE = process.env.E2E_BASE_URL || "http://localhost:3001";
export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@mocker.app";
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "changeme-admin";
export const TEST_EMAIL = "uitest@mocker.app";
export const TEST_PASSWORD = "uitest-password-1";
export const STORAGE_STATE = "e2e/.auth/user.json";

export async function apiLogin(email: string, password: string): Promise<string> {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`login as ${email} failed: ${res.status}`);
  const cookie = res.headers.get("set-cookie") ?? "";
  const token = /mocker_token=([^;]+)/.exec(cookie)?.[1];
  if (!token) throw new Error("no mocker_token cookie in login response");
  return token;
}

export async function adminFetch(token: string, path: string, init: RequestInit = {}) {
  return fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Cookie: `mocker_token=${token}`, ...init.headers },
  });
}
