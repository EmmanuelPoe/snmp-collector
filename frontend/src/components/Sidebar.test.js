import React from 'react';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from './Sidebar';
import * as api from '../services/api';

jest.mock('../services/api');

function loginAs(role) {
  const payload = btoa(JSON.stringify({ sub: 'u@test.com', role }));
  localStorage.setItem('snmp_access_token', `h.${payload}.s`);
}

// Await the first poll so its state updates land inside act().
const renderSidebar = () =>
  act(async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Sidebar />
      </MemoryRouter>,
    );
  });

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  api.getFleetSummary.mockResolvedValue({ alerts: { open: 120 } });
  api.getTraps.mockResolvedValue([]);
});

test('groups navigation and shows the Admin section only to admins', async () => {
  loginAs('admin');
  await renderSidebar();
  for (const heading of ['Monitor', 'Collection', 'Alerting', 'Admin']) {
    expect(screen.getByText(heading)).toBeInTheDocument();
  }
  expect(screen.getByRole('link', { name: /audit log/i })).toBeInTheDocument();
});

test('viewers do not see Admin links', async () => {
  loginAs('viewer');
  await renderSidebar();
  expect(screen.queryByText('Admin', { selector: '.sidebar-section-label' })).toBeNull();
  expect(screen.queryByRole('link', { name: /users/i })).toBeNull();
});

test('caps the alert badge at 99+', async () => {
  loginAs('viewer');
  await renderSidebar();
  expect(await screen.findByText('99+')).toBeInTheDocument();
});

test('theme button cycles and sets data-theme', async () => {
  loginAs('viewer');
  const user = userEvent.setup();
  await renderSidebar();
  await user.click(screen.getByRole('button', { name: /theme: system/i }));
  expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  await user.click(screen.getByRole('button', { name: /theme: light/i }));
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
});
