// Playwright E2E config (Step 3.5 / plan Step 24). Runs against the compose
// stack (nginx on :80) — `make up` first. In CI this runs inside the
// e2e-simulation job before scripts/run_simulation.sh.
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 120_000,
  // One worker, no retries: the spec is a sequential story (bootstrap login →
  // password change → device add → metrics), not independent tests.
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost',
    trace: 'retain-on-failure',
  },
});
