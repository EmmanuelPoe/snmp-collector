import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter } from 'react-router-dom';
import DeviceMetrics from './DeviceMetrics';
import * as api from '../services/api';

jest.mock('../services/api');

const DEVICES = [
  { id: 1, name: 'sw-a', ip_address: '10.0.0.1', enabled: true },
  { id: 2, name: 'sw-b', ip_address: '10.0.0.2', enabled: true },
];

beforeEach(() => {
  jest.clearAllMocks();
  api.getDevices.mockResolvedValue(DEVICES);
  api.getInterfaceRates.mockResolvedValue({ interfaces: {} });
});

function renderAt(route) {
  return render(
    <MemoryRouter
      initialEntries={[route]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Link to="/metrics?device_id=2">to b</Link>
      <DeviceMetrics />
    </MemoryRouter>,
  );
}

test('preselects the device from ?device_id= on load', async () => {
  renderAt('/metrics?device_id=1');
  await waitFor(() => expect(api.getInterfaceRates).toHaveBeenCalledWith('1'));
});

test('switches device when ?device_id= changes while already on the page', async () => {
  const user = userEvent.setup();
  renderAt('/metrics?device_id=1');
  await waitFor(() => expect(api.getInterfaceRates).toHaveBeenCalledWith('1'));

  await user.click(screen.getByText('to b'));
  await waitFor(() => expect(api.getInterfaceRates).toHaveBeenCalledWith('2'));
});
