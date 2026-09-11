import { useEffect, useRef } from 'react';
import { refreshSession } from '../services/api';
import { useToast } from '../hooks/useToast';

// Session lifetime owner (Step 6.1). Reads the access token's `exp` and, on a
// short tick:
//   • while the user is active, silently refreshes the token as it nears expiry
//     (sliding idle window, bounded server-side by the absolute cap);
//   • while idle, lets the token lapse and warns just before it does.
// A lapsed token → 401 → the api.js response interceptor redirects to /login.
const CHECK_INTERVAL_MS = 20 * 1000;
const ACTIVE_WINDOW_MS = 5 * 60 * 1000; // "active" = input within the last 5 min
const REFRESH_UNDER_S = 5 * 60; // refresh when active and this close to expiry
const WARN_UNDER_S = 2 * 60; // warn when idle and this close to expiry

function tokenExpirySeconds() {
  const token = localStorage.getItem('snmp_access_token');
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null; // malformed token — treat as no session
  }
}

export default function SessionMonitor() {
  const { showToast } = useToast();
  const lastActivityRef = useRef(Date.now());
  const warnedRef = useRef(false);

  useEffect(() => {
    const markActive = () => {
      lastActivityRef.current = Date.now();
    };
    const events = ['mousedown', 'keydown', 'touchstart'];
    events.forEach((evt) => window.addEventListener(evt, markActive, { passive: true }));

    const tick = async () => {
      const exp = tokenExpirySeconds();
      if (exp === null) {
        warnedRef.current = false;
        return;
      }
      const secondsLeft = exp - Date.now() / 1000;
      if (secondsLeft <= 0) return; // already expired — interceptor handles the 401

      const active = Date.now() - lastActivityRef.current < ACTIVE_WINDOW_MS;
      if (active && secondsLeft < REFRESH_UNDER_S) {
        try {
          await refreshSession();
          warnedRef.current = false; // window slid forward
        } catch {
          /* refresh rejected (e.g. absolute cap reached) → 401 handled elsewhere */
        }
        return;
      }
      if (secondsLeft > WARN_UNDER_S) {
        warnedRef.current = false; // plenty of time left; re-arm the warning
      } else if (!warnedRef.current) {
        warnedRef.current = true;
        showToast('Your session is about to expire — move the mouse or press a key to stay signed in.', 'warning');
      }
    };

    const interval = setInterval(tick, CHECK_INTERVAL_MS);
    return () => {
      clearInterval(interval);
      events.forEach((evt) => window.removeEventListener(evt, markActive));
    };
  }, [showToast]);

  return null;
}
