import { useEffect, useState } from 'react';

// Canvas/WebGL libraries (Cytoscape) can't use var(--x); read the resolved value.
export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Bumps whenever the theme changes (explicit toggle or OS preference), so
// components that bake colours into canvas styles can recompute them.
export function useThemeVersion() {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    document.documentElement.addEventListener('themechange', bump);
    mq?.addEventListener?.('change', bump);
    return () => {
      document.documentElement.removeEventListener('themechange', bump);
      mq?.removeEventListener?.('change', bump);
    };
  }, []);
  return version;
}
