import React from 'react';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { CommandPaletteProvider } from './CommandPalette';
import * as api from '../services/api';

jest.mock('../services/api');

function loginAs(role) {
  const payload = btoa(JSON.stringify({ sub: 'u@test.com', role }));
  localStorage.setItem('snmp_access_token', `h.${payload}.s`);
}

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname + loc.search}</div>;
}

function renderApp() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <CommandPaletteProvider>
        <input aria-label="some field" />
        <Where />
      </CommandPaletteProvider>
    </MemoryRouter>,
  );
}

const DEVICES = {
  items: [
    { id: 3, name: 'core-sw-003', ip_address: '10.1.0.3', enabled: true },
    { id: 4, name: 'core-sw-004', ip_address: '10.1.0.4', enabled: false },
  ],
  total: 2,
};

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  loginAs('admin');
  api.searchDevices.mockResolvedValue(DEVICES);
});

const palette = () => screen.getByRole('dialog', { name: /command palette/i });
const where = () => screen.getByTestId('where').textContent;

test('Ctrl+K opens and closes the palette; focus returns where it was', async () => {
  const user = userEvent.setup();
  renderApp();
  screen.getByLabelText('some field').focus();

  await user.keyboard('{Control>}k{/Control}');
  expect(palette()).toBeInTheDocument();
  expect(screen.getByRole('combobox')).toHaveFocus();

  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByLabelText('some field')).toHaveFocus();
});

test('"/" opens it, but not while typing in a field', async () => {
  const user = userEvent.setup();
  renderApp();

  await user.click(screen.getByLabelText('some field'));
  await user.keyboard('/');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

  await user.click(document.body);
  await user.keyboard('/');
  expect(palette()).toBeInTheDocument();
});

test('lists pages and actions with an empty query, and Admin pages only for admins', async () => {
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');

  const options = within(palette())
    .getAllByRole('option')
    .map((o) => o.textContent);
  expect(options.some((t) => t.startsWith('Audit Log'))).toBe(true);
  expect(options.some((t) => t.startsWith('Sign out'))).toBe(true);
  expect(api.searchDevices).not.toHaveBeenCalled();
});

test('viewers do not get admin pages', async () => {
  loginAs('viewer');
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  expect(within(palette()).queryByText('Audit Log')).toBeNull();
});

test('typing searches devices server-side and Enter opens the active page', async () => {
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'topo');

  // Page match is first, so Enter goes there.
  expect(await within(palette()).findByText('Topology')).toBeInTheDocument();
  await user.keyboard('{Enter}');
  expect(where()).toBe('/topology');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('device results: enabled opens metrics, disabled opens the device list filtered', async () => {
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'core');

  await waitFor(() =>
    expect(api.searchDevices).toHaveBeenLastCalledWith(
      'core',
      expect.objectContaining({ limit: 8 }),
    ),
  );
  await user.click(await within(palette()).findByText('core-sw-003'));
  expect(where()).toBe('/metrics?device_id=3');

  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'core');
  expect(await within(palette()).findByText('disabled')).toBeInTheDocument();
  await user.click(within(palette()).getByText('core-sw-004'));
  expect(where()).toBe('/devices?q=core-sw-004');
});

test('offers "show all" when more devices match than fit', async () => {
  api.searchDevices.mockResolvedValue({ ...DEVICES, total: 1500 });
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'core');

  await user.click(await within(palette()).findByText('Show all 1,500 matching devices'));
  expect(where()).toBe('/devices?q=core');
});

test('arrow keys move the active option and wrap', async () => {
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  const input = screen.getByRole('combobox');
  const options = () => within(palette()).getAllByRole('option');

  expect(options()[0]).toHaveAttribute('aria-selected', 'true');
  await user.keyboard('{ArrowUp}');
  expect(options()[options().length - 1]).toHaveAttribute('aria-selected', 'true');
  expect(input).toHaveAttribute('aria-activedescendant', `palette-opt-${options().length - 1}`);
  await user.keyboard('{ArrowDown}');
  expect(options()[0]).toHaveAttribute('aria-selected', 'true');
});

test('shows a note when device search fails, and still finds pages', async () => {
  api.searchDevices.mockRejectedValue(new Error('boom'));
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'dash');

  expect(await within(palette()).findByText('Device search unavailable')).toBeInTheDocument();
  expect(within(palette()).getByText('Dashboard')).toBeInTheDocument();
});

test('an out-of-order slow response cannot overwrite a newer search', async () => {
  let resolveSlow;
  api.searchDevices.mockImplementation((term) =>
    term === 'co'
      ? new Promise((res) => {
          resolveSlow = () =>
            res({ items: [{ id: 1, name: 'STALE-co', ip_address: '1', enabled: true }], total: 1 });
        })
      : Promise.resolve({
          items: [{ id: 2, name: 'fresh-cor', ip_address: '2', enabled: true }],
          total: 1,
        }),
  );
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  const input = screen.getByRole('combobox');
  await user.type(input, 'co');
  await waitFor(() => expect(api.searchDevices).toHaveBeenCalledWith('co', expect.anything()));
  await user.type(input, 'r');
  expect(await within(palette()).findByText('fresh-cor')).toBeInTheDocument();

  await act(async () => resolveSlow());
  expect(within(palette()).queryByText('STALE-co')).toBeNull();
});

test('Switch theme action cycles the theme', async () => {
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'theme');
  await user.keyboard('{Enter}');
  expect(document.documentElement.getAttribute('data-theme')).toBe('light');
});

test('ignores keydown events that have no key (autofill / synthetic events)', () => {
  renderApp();
  expect(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { ctrlKey: true }));
  }).not.toThrow();
});

test('does not open over another dialog, so a half-filled form survives', async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <CommandPaletteProvider>
        <div className="modal-overlay">
          <button>modal button</button>
        </div>
      </CommandPaletteProvider>
    </MemoryRouter>,
  );
  await user.click(screen.getByText('modal button'));
  await user.keyboard('{Control>}k{/Control}');
  await user.keyboard('/');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('is inert when signed out', async () => {
  localStorage.clear();
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('changing the text drops the previous query device rows immediately', async () => {
  api.searchDevices.mockImplementation(
    (term) => (term === 'core' ? Promise.resolve(DEVICES) : new Promise(() => {})), // never resolves: the "edge" search stays in flight
  );
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  const input = screen.getByRole('combobox');
  await user.type(input, 'core');
  expect(await within(palette()).findByText('core-sw-003')).toBeInTheDocument();

  await user.clear(input);
  await user.type(input, 'edge');
  expect(within(palette()).queryByText('core-sw-003')).toBeNull();
  await user.keyboard('{Enter}'); // must not navigate to a stale device
  expect(where()).not.toMatch(/metrics/);
});

test('Enter while composing text (IME) does not select a result', async () => {
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  const input = screen.getByRole('combobox');

  const composing = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
  Object.defineProperty(composing, 'isComposing', { value: true });
  await act(async () => {
    input.dispatchEvent(composing);
  });
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(where()).toBe('/');
});

test('late device results do not move the highlighted row', async () => {
  let resolve;
  api.searchDevices.mockImplementation(() => new Promise((r) => (resolve = r)));
  const user = userEvent.setup();
  renderApp();
  await user.keyboard('{Control>}k{/Control}');
  await user.type(screen.getByRole('combobox'), 'o'); // matches several pages (Monitor, Topology, ...)
  await user.keyboard('{ArrowDown}{ArrowDown}');
  const highlighted = () =>
    within(palette())
      .getAllByRole('option')
      .find((o) => o.getAttribute('aria-selected') === 'true').textContent;
  await waitFor(() => expect(api.searchDevices).toHaveBeenCalled()); // past the debounce
  const before = highlighted();

  await act(async () => resolve(DEVICES));
  expect(highlighted()).toBe(before);
});
