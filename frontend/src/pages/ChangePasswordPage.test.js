import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChangePasswordPage from './ChangePasswordPage';
import { changePassword } from '../services/api';

jest.mock('../services/api', () => ({
  changePassword: jest.fn(),
}));

const mockNavigate = jest.fn();
let mockLocationState;
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  useLocation: () => ({ state: mockLocationState }),
}));

// The three password inputs share a type and have no htmlFor/id pairing; index
// them in DOM order: current, new, confirm.
function fields() {
  const inputs = document.querySelectorAll('input[type="password"]');
  return { current: inputs[0], next: inputs[1], confirm: inputs[2] };
}
function submit() {
  return screen.getByRole('button', { name: /set new password/i });
}

async function fill(user, { current, next, confirm }) {
  const f = fields();
  await user.type(f.current, current);
  await user.type(f.next, next);
  await user.type(f.confirm, confirm);
}

beforeEach(() => {
  jest.clearAllMocks();
  mockLocationState = { forced: true };
});

test('a successful change navigates to the dashboard', async () => {
  const user = userEvent.setup();
  changePassword.mockResolvedValue({});
  render(<ChangePasswordPage />);

  await fill(user, { current: 'old-password', next: 'Nw-Passw0rd!', confirm: 'Nw-Passw0rd!' });
  await user.click(submit());

  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
  expect(changePassword).toHaveBeenCalledWith('old-password', 'Nw-Passw0rd!');
});

test('mismatched confirmation is rejected without calling the API', async () => {
  const user = userEvent.setup();
  render(<ChangePasswordPage />);

  await fill(user, { current: 'old-password', next: 'Nw-Passw0rd!', confirm: 'Different!23' });
  await user.click(submit());

  expect(await screen.findByText('New passwords do not match.')).toBeInTheDocument();
  expect(changePassword).not.toHaveBeenCalled();
  expect(mockNavigate).not.toHaveBeenCalled();
});

test('a too-short password is rejected without calling the API', async () => {
  const user = userEvent.setup();
  render(<ChangePasswordPage />);

  await fill(user, { current: 'old-password', next: 'short', confirm: 'short' });
  await user.click(submit());

  expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
  expect(changePassword).not.toHaveBeenCalled();
});

test('a server rejection surfaces its detail and re-enables the form', async () => {
  const user = userEvent.setup();
  changePassword.mockRejectedValue({
    response: { data: { detail: 'Password was used recently' } },
  });
  render(<ChangePasswordPage />);

  await fill(user, { current: 'old-password', next: 'Nw-Passw0rd!', confirm: 'Nw-Passw0rd!' });
  await user.click(submit());

  expect(await screen.findByText('Password was used recently')).toBeInTheDocument();
  expect(mockNavigate).not.toHaveBeenCalled();
  expect(submit()).toBeEnabled();
});

test('a detail-less failure falls back to a generic message', async () => {
  const user = userEvent.setup();
  changePassword.mockRejectedValue(new Error('network down'));
  render(<ChangePasswordPage />);

  await fill(user, { current: 'old-password', next: 'Nw-Passw0rd!', confirm: 'Nw-Passw0rd!' });
  await user.click(submit());

  expect(await screen.findByText('Failed to change password.')).toBeInTheDocument();
});

test('the forced-change notice is hidden when the visit is voluntary', () => {
  mockLocationState = { forced: false };
  render(<ChangePasswordPage />);

  expect(screen.queryByText(/must set a new password/i)).not.toBeInTheDocument();
});

test('the forced-change notice shows when no route state was passed', () => {
  mockLocationState = undefined;
  render(<ChangePasswordPage />);

  expect(screen.getByText(/must set a new password/i)).toBeInTheDocument();
});
