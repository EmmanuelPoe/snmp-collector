import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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
  api.getDevices.mockResolvedValue([]);
  api.getAgents.mockResolvedValue([]);
  api.getInterfaceRates.mockResolvedValue([]);
  api.getDeviceTags.mockResolvedValue([]);
  api.getAlerts.mockResolvedValue([ALERT]);
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

  const dropdown = await screen.findByRole('combobox');
  await user.selectOptions(dropdown, '1');

  await waitFor(() => expect(api.assignAlert).toHaveBeenCalledWith(42, 1));
});
