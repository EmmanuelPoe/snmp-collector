// Happy-path E2E (Step 3.5 / plan Step 24) against the compose stack:
// bootstrap login → forced password change → add the SNMP simulator as a
// device → wait for metrics to flow → dashboard chart + alert feed render.
//
// Required env:
//   E2E_BOOTSTRAP_PASSWORD — one-time bootstrap admin password (CI greps it
//                            from the backend log). The test changes it to
//                            E2E_NEW_PASSWORD; pass that to run_simulation.sh
//                            as SIM_ADMIN_PASSWORD afterwards.
const { test, expect } = require('@playwright/test');

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@localhost';
const BOOTSTRAP_PASSWORD = process.env.E2E_BOOTSTRAP_PASSWORD;
const NEW_PASSWORD = process.env.E2E_NEW_PASSWORD || 'E2e-Playwright!234';
const DEVICE_NAME = 'E2E-Simulator';
const DEVICE_IP = process.env.E2E_DEVICE_IP || 'snmp-simulator';
const METRICS_WAIT_MS = 300_000; // agent config fetch + poll cycle is ~2 min worst case

test('bootstrap login → add device → metrics flow → dashboard renders', async ({ page }) => {
  test.setTimeout(480_000);
  expect(BOOTSTRAP_PASSWORD, 'E2E_BOOTSTRAP_PASSWORD must be set').toBeTruthy();

  await test.step('login with the bootstrap password lands on forced password change', async () => {
    await page.goto('/login');
    await page.locator('input[type=email]').fill(ADMIN_EMAIL);
    await page.locator('input[type=password]').fill(BOOTSTRAP_PASSWORD);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/change-password/);
    await expect(page.getByText(/set a new password before continuing/i)).toBeVisible();
  });

  await test.step('set a new password and land on the dashboard', async () => {
    const pw = page.locator('input[type=password]');
    await pw.nth(0).fill(BOOTSTRAP_PASSWORD);
    await pw.nth(1).fill(NEW_PASSWORD);
    await pw.nth(2).fill(NEW_PASSWORD);
    await page.getByRole('button', { name: /set new password/i }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByText('Network Traffic · Per Device')).toBeVisible();
    await expect(page.getByText('Active Alerts')).toBeVisible();
  });

  await test.step('add the SNMP simulator as a device', async () => {
    await page.goto('/devices');
    await page.getByRole('button', { name: /add device/i }).click();
    await page.getByPlaceholder('e.g., Router-01').fill(DEVICE_NAME);
    await page.getByPlaceholder('192.168.1.1').fill(DEVICE_IP);
    await page.getByRole('button', { name: /^create$/i }).click();
    await expect(page.getByText(DEVICE_NAME).first()).toBeVisible();
  });

  await test.step('metrics arrive from the agent within the poll cycle', async () => {
    await expect
      .poll(
        async () => {
          return page.evaluate(async () => {
            const token = localStorage.getItem('snmp_access_token');
            const headers = { Authorization: `Bearer ${token}` };
            const devices = await (await fetch('/api/devices', { headers })).json();
            const device = devices.find((d) => d.name === 'E2E-Simulator');
            if (!device) return 0;
            const resp = await fetch(`/api/metrics/latest/${device.id}?limit=1`, { headers });
            if (!resp.ok) return 0;
            const rows = await resp.json();
            return Array.isArray(rows) ? rows.length : 0;
          });
        },
        { timeout: METRICS_WAIT_MS, intervals: [10_000] },
      )
      .toBeGreaterThan(0);
  });

  await test.step('dashboard traffic chart renders with data', async () => {
    await page.goto('/');
    await expect(page.locator('.recharts-surface').first()).toBeVisible({ timeout: 60_000 });
  });
});
