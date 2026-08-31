import { defineConfig } from "@playwright/test";

// Smoke tests against the RUNNING dev stack (docker compose up), mirroring the backend suite's
// live-server philosophy. Global setup provisions a throwaway account through the admin API and
// tears it down afterwards, so runs never pollute real users' stats or the leaderboard.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // one user, sequential flows
  retries: 0,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3001",
    trace: "retain-on-failure",
  },
  globalSetup: "./e2e/global-setup",
  globalTeardown: "./e2e/global-teardown",
});
