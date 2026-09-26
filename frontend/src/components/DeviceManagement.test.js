import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DeviceManagement from './DeviceManagement';
import { ToastProvider } from '../hooks/useToast';
import * as api from '../services/api';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => jest.fn(),
}));
jest.mock('../services/api');

const DEVICE = {
  id: 7,
  name: 'sw-edge-1',
  ip_address: '10.0.0.7',
  snmp_version: '2c',
  snmp_port: 161,
  snmp_modules: ['if_mib'],
  device_type: 'switch',
  description: '',
  enabled: true,
  username: null,
  auth_protocol: null,
  priv_protocol: null,
  assigned_agent_id: null,
  tags: [],
};

function renderPage() {
  return render(
    <ToastProvider>
      <DeviceManagement />
    </ToastProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  api.getDevices.mockResolvedValue([]);
  api.getModules.mockResolvedValue(['if_mib']);
  api.getAgents.mockResolvedValue([]);
  api.getDeviceTags.mockResolvedValue([]);
  api.getAlertRules.mockRejectedValue({ response: { status: 404 } });
  api.getDeviceCredentials.mockResolvedValue({
    snmp_community: 'public',
    username: null,
    auth_protocol: null,
    priv_protocol: null,
  });
  api.createDevice.mockResolvedValue({ ...DEVICE, id: 9, name: 'new-switch' });
  api.updateDevice.mockResolvedValue(DEVICE);
  api.saveAlertRules.mockResolvedValue({});
});

test('create flow: fills the modal and calls createDevice with the form data', async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(await screen.findByRole('button', { name: /add device/i }));

  await user.type(screen.getByPlaceholderText('e.g., Router-01'), 'new-switch');
  await user.type(screen.getByPlaceholderText('192.168.1.1'), '10.0.0.9');
  await user.click(screen.getByRole('button', { name: /^create$/i }));

  await waitFor(() => expect(api.createDevice).toHaveBeenCalledTimes(1));
  const payload = api.createDevice.mock.calls[0][0];
  expect(payload.name).toBe('new-switch');
  expect(payload.ip_address).toBe('10.0.0.9');
  // v2c create: v3 credential fields are nulled out
  expect(payload.username).toBeNull();
  expect(payload.auth_password).toBeNull();
  // no thresholds entered -> no alert-rule upsert
  expect(api.saveAlertRules).not.toHaveBeenCalled();
});

test('create flow with alert thresholds also upserts alert rules', async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(await screen.findByRole('button', { name: /add device/i }));

  await user.type(screen.getByPlaceholderText('e.g., Router-01'), 'new-switch');
  await user.type(screen.getByPlaceholderText('192.168.1.1'), '10.0.0.9');
  // The two bandwidth threshold inputs share a placeholder: [in, out].
  const thresholdInputs = screen.getAllByPlaceholderText('e.g. 80');
  await user.type(thresholdInputs[0], '75');
  await user.click(screen.getByRole('button', { name: /^create$/i }));

  await waitFor(() => expect(api.saveAlertRules).toHaveBeenCalledTimes(1));
  expect(api.saveAlertRules).toHaveBeenCalledWith(9, {
    bandwidth_in_pct: 75,
    bandwidth_out_pct: null,
    error_rate: null,
    enabled: true,
  });
});

test('edit flow: loads the device into the modal and calls updateDevice', async () => {
  const user = userEvent.setup();
  api.getDevices.mockResolvedValue([DEVICE]);
  renderPage();

  await user.click(await screen.findByRole('button', { name: /edit/i }));
  const nameInput = await screen.findByDisplayValue('sw-edge-1');
  await user.clear(nameInput);
  await user.type(nameInput, 'sw-edge-renamed');
  await user.click(screen.getByRole('button', { name: /^update$/i }));

  await waitFor(() => expect(api.updateDevice).toHaveBeenCalledTimes(1));
  const [id, payload] = api.updateDevice.mock.calls[0];
  expect(id).toBe(7);
  expect(payload.name).toBe('sw-edge-renamed');
});
