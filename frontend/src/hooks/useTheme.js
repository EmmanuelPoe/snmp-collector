import { useCallback, useEffect, useRef, useState } from 'react';

const KEY = 'snmp-theme';
const CHOICES = ['system', 'light', 'dark'];

function readStored() {
  try {
    const v = localStorage.getItem(KEY);
    return CHOICES.includes(v) ? v : 'system';
  } catch {
    return 'system'; // storage blocked: still render, just don't remember
  }
}

// 'system' leaves data-theme unset so the prefers-color-scheme block applies.
export function applyTheme(choice) {
  const root = document.documentElement;
  if (choice === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', choice);
  root.dispatchEvent(new CustomEvent('themechange', { detail: choice }));
}

export function initTheme() {
  applyTheme(readStored());
}

export function useTheme() {
  const [theme, setThemeState] = useState(readStored);
  const mounted = useRef(false);

  // initTheme() already applied the stored choice at startup; re-applying on
  // mount would fire a redundant themechange (rebuilding every canvas chart).
  useEffect(() => {
    if (mounted.current) applyTheme(theme);
    mounted.current = true;
  }, [theme]);

  // Follow a change made in another tab.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === KEY) setThemeState(readStored());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const setTheme = useCallback((next) => {
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // not persisted; applies for this session
    }
    setThemeState(next);
  }, []);

  const cycle = useCallback(() => {
    setTheme(CHOICES[(CHOICES.indexOf(theme) + 1) % CHOICES.length]);
  }, [theme, setTheme]);

  return { theme, setTheme, cycle };
}
