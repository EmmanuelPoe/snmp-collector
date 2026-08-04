import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginPage from './LoginPage';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

function mockLoginResponse(status, body) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

// The inputs have no htmlFor/id pairing; fall back to placeholder queries.
function emailInput() {
  return screen.getByPlaceholderText('admin@localhost');
}
function passwordInput() {
  return screen.getByPlaceholderText('••••••••');
}

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
});

test('successful login stores the token and navigates to the dashboard', async () => {
  const user = userEvent.setup();
  mockLoginResponse(200, { access_token: 'h.p.s', force_password_change: false });
  render(<LoginPage />);

  await user.type(emailInput(), 'admin@test.com');
  await user.type(passwordInput(), 'pw12345678');
  await user.click(screen.getByRole('button', { name: /sign in/i }));

  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { state: undefined }));
  expect(localStorage.getItem('snmp_access_token')).toBe('h.p.s');
});

test('failed login shows an error and does not navigate', async () => {
  const user = userEvent.setup();
  mockLoginResponse(401, { detail: 'Incorrect email or password' });
  render(<LoginPage />);

  await user.type(emailInput(), 'admin@test.com');
  await user.type(passwordInput(), 'wrong-password');
  await user.click(screen.getByRole('button', { name: /sign in/i }));

  expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument();
  expect(mockNavigate).not.toHaveBeenCalled();
  expect(localStorage.getItem('snmp_access_token')).toBeNull();
});

test('locked account (423) shows the lockout message', async () => {
  const user = userEvent.setup();
  mockLoginResponse(423, { detail: 'locked' });
  render(<LoginPage />);

  await user.type(emailInput(), 'admin@test.com');
  await user.type(passwordInput(), 'pw12345678');
  await user.click(screen.getByRole('button', { name: /sign in/i }));

  expect(await screen.findByText(/temporarily locked/i)).toBeInTheDocument();
  expect(mockNavigate).not.toHaveBeenCalled();
});

test('forced password change redirects to /change-password', async () => {
  const user = userEvent.setup();
  mockLoginResponse(200, { access_token: 'h.p.s', force_password_change: true });
  render(<LoginPage />);

  await user.type(emailInput(), 'admin@test.com');
  await user.type(passwordInput(), 'bootstrap-pw');
  await user.click(screen.getByRole('button', { name: /sign in/i }));

  await waitFor(() =>
    expect(mockNavigate).toHaveBeenCalledWith('/change-password', { state: { forced: true } }),
  );
});
