import React from 'react';
import { render, act } from '@testing-library/react';
import SessionMonitor from './SessionMonitor';
import { refreshSession } from '../services/api';

jest.mock('../services/api', () => ({
  refreshSession: jest.fn(),
}));

const mockShowToast = jest.fn();
jest.mock('../hooks/useToast', () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

// The monitor reads `exp` out of the token payload; build one that expires in
// `secondsFromNow`. Only the payload segment is ever parsed.
function setToken(secondsFromNow) {
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + secondsFromNow }));
  localStorage.setItem('snmp_access_token', `h.${payload}.s`);
}

const CHECK_INTERVAL_MS = 20 * 1000;
const IDLE_MS = 6 * 60 * 1000; // past ACTIVE_WINDOW_MS (5 min)

// Fake timers also freeze Date.now(), so advancing the clock ages the token
// too — go idle *before* minting the near-expiry token.
async function advance(ms) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

const tick = () => advance(CHECK_INTERVAL_MS);

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

test('refreshes silently when the user is active and expiry is near', async () => {
  setToken(60); // inside REFRESH_UNDER_S (5 min)
  refreshSession.mockResolvedValue({});
  render(<SessionMonitor />);

  await tick();

  expect(refreshSession).toHaveBeenCalledTimes(1);
  expect(mockShowToast).not.toHaveBeenCalled();
});

test('warns once when idle and expiry is near', async () => {
  render(<SessionMonitor />);
  await advance(IDLE_MS); // no token yet; the user simply goes idle
  setToken(60); // inside WARN_UNDER_S (2 min)

  await tick();

  expect(refreshSession).not.toHaveBeenCalled();
  expect(mockShowToast).toHaveBeenCalledTimes(1);
  expect(mockShowToast).toHaveBeenCalledWith(expect.stringMatching(/about to expire/i), 'warning');

  // Still idle and still near expiry — the warning must not repeat.
  await tick();
  expect(mockShowToast).toHaveBeenCalledTimes(1);
});

test('does nothing without a token', async () => {
  render(<SessionMonitor />);

  await tick();

  expect(refreshSession).not.toHaveBeenCalled();
  expect(mockShowToast).not.toHaveBeenCalled();
});

test('does nothing with a malformed token', async () => {
  localStorage.setItem('snmp_access_token', 'not-a-jwt');
  render(<SessionMonitor />);

  await tick();

  expect(refreshSession).not.toHaveBeenCalled();
  expect(mockShowToast).not.toHaveBeenCalled();
});

test('a far-off expiry neither refreshes nor warns', async () => {
  setToken(60 * 60);
  render(<SessionMonitor />);

  await tick();

  expect(refreshSession).not.toHaveBeenCalled();
  expect(mockShowToast).not.toHaveBeenCalled();
});

test('a rejected refresh is swallowed', async () => {
  setToken(60);
  refreshSession.mockRejectedValue(new Error('absolute cap reached'));
  render(<SessionMonitor />);

  await tick();

  expect(refreshSession).toHaveBeenCalledTimes(1);
  expect(mockShowToast).not.toHaveBeenCalled();
});

test('user input re-arms the active window', async () => {
  refreshSession.mockResolvedValue({});
  render(<SessionMonitor />);

  // Go idle, take the warning, then show activity again.
  await advance(IDLE_MS);
  setToken(60);
  await tick();
  expect(mockShowToast).toHaveBeenCalledTimes(1);
  expect(refreshSession).not.toHaveBeenCalled();

  await act(async () => {
    window.dispatchEvent(new Event('keydown'));
  });
  await tick();

  expect(refreshSession).toHaveBeenCalledTimes(1);
});

test('unmounting stops the ticker', async () => {
  setToken(60);
  refreshSession.mockResolvedValue({});
  const { unmount } = render(<SessionMonitor />);

  unmount();
  await tick();

  expect(refreshSession).not.toHaveBeenCalled();
});
