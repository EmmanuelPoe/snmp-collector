import { useCallback, useEffect, useState } from 'react';

// One timer and one in-flight request per key, however many components (or
// browser tabs' worth of widgets) subscribe. Polling pauses while the tab is
// hidden, resumes immediately on return, and backs off after failures so a
// struggling backend isn't hammered by every open dashboard.
const MAX_BACKOFF_STEPS = 4; // 30s base -> 8m cap

const entries = new Map();

function schedule(entry) {
  clearTimeout(entry.timer);
  if (entry.subs.size === 0) return;
  const delay = entry.intervalMs * 2 ** Math.min(entry.failures, MAX_BACKOFF_STEPS);
  entry.timer = setTimeout(() => run(entry), delay);
}

async function run(entry) {
  if (entry.inflight) return entry.inflight;
  if (typeof document !== 'undefined' && document.hidden) {
    entry.stale = true; // visibilitychange triggers the catch-up fetch
    return undefined;
  }
  entry.stale = false;
  entry.inflight = (async () => {
    try {
      entry.state = { data: await entry.fetcher(), error: null, updatedAt: Date.now() };
      entry.failures = 0;
    } catch (error) {
      entry.state = { ...entry.state, error };
      entry.failures += 1;
    } finally {
      entry.inflight = null;
      entry.subs.forEach((notify) => notify(entry.state));
      schedule(entry);
    }
  })();
  return entry.inflight;
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    entries.forEach((entry) => {
      if (entry.stale && entry.subs.size > 0) run(entry);
    });
  });
}

export function usePolledResource(key, fetcher, { intervalMs = 30000 } = {}) {
  const [state, setState] = useState(() => entries.get(key)?.state || { data: null, error: null });

  useEffect(() => {
    let entry = entries.get(key);
    if (!entry) {
      entry = {
        subs: new Set(),
        state: { data: null, error: null, updatedAt: null },
        failures: 0,
        stale: false,
      };
      entries.set(key, entry);
    }
    entry.fetcher = fetcher;
    entry.intervalMs = intervalMs;
    entry.subs.add(setState);
    // Always resync: a new key must not keep showing the previous key's data/error.
    setState(entry.state);
    // Join a fresh result instead of refetching when a second consumer mounts.
    if (!entry.state.updatedAt || Date.now() - entry.state.updatedAt >= intervalMs) run(entry);
    else schedule(entry);
    return () => {
      entry.subs.delete(setState);
      if (entry.subs.size === 0) {
        clearTimeout(entry.timer);
        entries.delete(key);
      }
    };
    // fetcher is keyed by `key`; callers pass a new closure each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, intervalMs]);

  const refresh = useCallback(() => {
    const entry = entries.get(key);
    return entry ? run(entry) : undefined;
  }, [key]);

  return { ...state, loading: !state.updatedAt && !state.error, refresh };
}
