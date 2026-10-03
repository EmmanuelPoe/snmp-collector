import { useCallback, useEffect, useState } from 'react';

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

  // Follow a change made elsewhere in this tab (e.g. the command palette).
  useEffect(() => {
    const root = document.documentElement;
    const onChange = (e) => CHOICES.includes(e.detail) && setThemeState(e.detail);
    root.addEventListener('themechange', onChange);
    return () => root.removeEventListener('themechange', onChange);
  }, []);

  // Follow a change made in another tab.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === KEY) applyTheme(readStored());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Applied synchronously, not from an effect: a caller may unmount right after
  // (the palette closes on select) and an effect would never run.
  const setTheme = useCallback((next) => {
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // not persisted; applies for this session
    }
    applyTheme(next); // its themechange event updates every hook instance, including this one
  }, []);

  const cycle = useCallback(() => {
    setTheme(CHOICES[(CHOICES.indexOf(theme) + 1) % CHOICES.length]);
  }, [theme, setTheme]);

  return { theme, setTheme, cycle };
}
