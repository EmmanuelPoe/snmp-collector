import { act, renderHook } from '@testing-library/react';
import { applyTheme, useTheme } from './useTheme';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

test('defaults to system and leaves data-theme unset so the OS preference applies', () => {
  const { result } = renderHook(() => useTheme());
  expect(result.current.theme).toBe('system');
  expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
});

test('cycles system -> light -> dark -> system, persisting and applying each', () => {
  const { result } = renderHook(() => useTheme());
  const seen = [];
  for (let i = 0; i < 3; i++) {
    act(() => result.current.cycle());
    seen.push([result.current.theme, document.documentElement.getAttribute('data-theme')]);
  }
  expect(seen).toEqual([
    ['light', 'light'],
    ['dark', 'dark'],
    ['system', null],
  ]);
  expect(localStorage.getItem('snmp-theme')).toBe('system');
});

test('restores a stored choice and ignores junk values', () => {
  localStorage.setItem('snmp-theme', 'dark');
  expect(renderHook(() => useTheme()).result.current.theme).toBe('dark');
  localStorage.setItem('snmp-theme', 'neon');
  expect(renderHook(() => useTheme()).result.current.theme).toBe('system');
});

test('still works when storage throws', () => {
  const spy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked');
  });
  const { result } = renderHook(() => useTheme());
  act(() => result.current.setTheme('dark'));
  expect(result.current.theme).toBe('dark');
  spy.mockRestore();
});

test('announces theme changes so canvas charts can recolour', () => {
  const handler = jest.fn();
  document.documentElement.addEventListener('themechange', handler);
  applyTheme('dark');
  expect(handler).toHaveBeenCalledTimes(1);
  document.documentElement.removeEventListener('themechange', handler);
});

test('does not re-announce the theme on mount, but follows other tabs', () => {
  const handler = jest.fn();
  document.documentElement.addEventListener('themechange', handler);
  const { result } = renderHook(() => useTheme());
  expect(handler).not.toHaveBeenCalled();

  act(() => {
    localStorage.setItem('snmp-theme', 'dark');
    window.dispatchEvent(new StorageEvent('storage', { key: 'snmp-theme' }));
  });
  expect(result.current.theme).toBe('dark');
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  document.documentElement.removeEventListener('themechange', handler);
});
