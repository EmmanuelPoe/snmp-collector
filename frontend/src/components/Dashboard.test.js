import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Dashboard from './Dashboard';
import { ToastProvider } from '../hooks/useToast';
import * as api from '../services/api';

jest.mock('../services/api');

const ALERT = {
  id: 42,
  device_id: 1,
  agent_id: null,
  alert_type: 'device_unreachable',
  severity: 'critical',
  message: 'Device sw-edge-1 (10.0.0.7) is unreachable',
  status: 'open',
  triggered_at: '2026-07-19T10:00:00Z',
  acknowledged_by_email: null,
  assigned_to: null,
  note: null,
};

const SUMMARY = {
  devices: { total: 2000, enabled: 1990, disabled: 10, up: 1950, degraded: 30, down: 10 },
  alerts: { open: 1, critical: 1, warning: 0, info: 0, unacknowledged: 1 },
  agents: { total: 2, online: 2, offline: 0 },
};

const TRAFFIC = {
  series: [{ timestamp: '2026-07-19T10:00:00Z', in_bps: 5e6, out_bps: 2e6, devices: 3 }],
  totals: { in_bps: 5e6, out_bps: 2e6, interfaces: 3, devices: 3 },
  top_by_traffic: [
    {
      device_ip: '10.0.0.7',
      device_name: 'sw-edge-1',
      interface_name: 'Gi0/1',
      in_bps: 4e6,
      out_bps: 1e6,
      utilization_pct: 0.4,
    },
  ],
  top_by_utilization: [],
};

function loginAs(role) {
  // useAuth derives the user from the JWT payload in localStorage.
  const payload = btoa(JSON.stringify({ sub: 'admin@test.com', role }));
  localStorage.setItem('snmp_access_token', `h.${payload}.s`);
}

function renderDashboard() {
  return render(
    <ToastProvider>
      <Dashboard />
    </ToastProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  api.getAgents.mockResolvedValue([]);
  api.getFleetSummary.mockResolvedValue(SUMMARY);
  api.getFleetTraffic.mockResolvedValue(TRAFFIC);
  api.getAlertsPage.mockResolvedValue({ items: [ALERT], total: 1 });
  api.getAssignableUsers.mockResolvedValue([{ id: 1, email: 'admin@test.com' }]);
  api.acknowledgeAlert.mockResolvedValue({ ...ALERT, acknowledged_by_email: 'admin@test.com' });
  api.assignAlert.mockResolvedValue({ ...ALERT, assigned_to: 1 });
  api.setAlertNote.mockResolvedValue({ ...ALERT, note: 'investigating' });
});

test('alert feed renders open alerts with severity and message', async () => {
  loginAs('viewer');
  renderDashboard();

  // The message shows in the feed row and again in the new-alert toast.
  expect((await screen.findAllByText(ALERT.message)).length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText('critical')).toBeInTheDocument();
  // Viewers get no management controls.
  expect(screen.queryByRole('button', { name: /acknowledge/i })).not.toBeInTheDocument();
});

test('editor can acknowledge an alert and the row updates', async () => {
  loginAs('editor');
  const user = userEvent.setup();
  renderDashboard();

  await user.click(await screen.findByRole('button', { name: /acknowledge/i }));

  await waitFor(() => expect(api.acknowledgeAlert).toHaveBeenCalledWith(42));
  expect(await screen.findByText(/ack admin@test.com/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /acknowledge/i })).not.toBeInTheDocument();
});

test('editor can assign an alert from the assignee dropdown', async () => {
  loginAs('editor');
  const user = userEvent.setup();
  renderDashboard();

  const dropdown = await screen.findByDisplayValue('Unassigned');
  await user.selectOptions(dropdown, '1');

  await waitFor(() => expect(api.assignAlert).toHaveBeenCalledWith(42, 1));
});

test('summary comes from the fleet endpoint, not a per-device fan-out', async () => {
  loginAs('viewer');
  renderDashboard();

  expect(await screen.findByText('2,000')).toBeInTheDocument();
  expect(screen.getByText(/1,950 up/)).toBeInTheDocument();
  expect(screen.getByText('sw-edge-1')).toBeInTheDocument();
  expect(api.getFleetSummary).toHaveBeenCalledTimes(1);
  expect(api.getFleetTraffic).toHaveBeenCalledWith(1, 10);
  expect(api.getDevices).not.toHaveBeenCalled();
  expect(api.getInterfaceRates).not.toHaveBeenCalled();
});

test('an alert burst collapses into a single toast and the backlog stays silent', async () => {
  loginAs('viewer');
  const mk = (id, severity) => ({ ...ALERT, id, severity, message: `alert ${id}` });
  api.getAlertsPage.mockResolvedValueOnce({ items: [mk(1, 'warning')], total: 1 });
  jest.useFakeTimers({ advanceTimers: true });
  try {
    renderDashboard();
    await screen.findByText('alert 1');
    // Backlog on first load: no toast.
    expect(screen.queryByText(/new alerts/)).not.toBeInTheDocument();

    api.getAlertsPage.mockResolvedValue({
      items: [
        mk(2, 'critical'),
        mk(3, 'critical'),
        mk(4, 'warning'),
        mk(5, 'warning'),
        mk(1, 'warning'),
      ],
      total: 5,
    });
    await act(async () => {
      jest.advanceTimersByTime(31000);
    });
    expect(await screen.findByText('4 new alerts (2 critical)')).toBeInTheDocument();
  } finally {
    jest.useRealTimers();
  }
});

test('severity filter and show-more refetch with server-side params', async () => {
  loginAs('viewer');
  const user = userEvent.setup();
  api.getAlertsPage.mockResolvedValue({ items: [ALERT], total: 120 });
  renderDashboard();

  await user.click(await screen.findByRole('button', { name: /show more \(119 remaining\)/i }));
  await waitFor(() => expect(api.getAlertsPage).toHaveBeenCalledWith({ limit: 100 }));
  await user.selectOptions(screen.getByLabelText(/filter alerts by severity/i), 'critical');
  await waitFor(() =>
    expect(api.getAlertsPage).toHaveBeenCalledWith({ limit: 50, severity: 'critical' }),
  );
});

test('shows an error with retry instead of an endless spinner when the summary fails', async () => {
  loginAs('viewer');
  const user = userEvent.setup();
  api.getFleetSummary.mockRejectedValueOnce(new Error('500'));
  renderDashboard();

  expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't load the fleet summary/i);
  await user.click(screen.getByRole('button', { name: /retry now/i }));
  expect(await screen.findByText('2,000')).toBeInTheDocument();
});

test('show-more does not announce older alerts as new', async () => {
  loginAs('viewer');
  const user = userEvent.setup();
  const mk = (id) => ({ ...ALERT, id, message: `alert ${id}` });
  api.getAlertsPage.mockImplementation(async ({ limit }) => ({
    items: Array.from({ length: Math.min(limit, 120) }, (_, i) => mk(200 - i)),
    total: 120,
  }));
  renderDashboard();

  await user.click(await screen.findByRole('button', { name: /show more/i }));
  await screen.findByText('alert 101');
  expect(screen.queryByText(/new alerts/)).not.toBeInTheDocument();
});
