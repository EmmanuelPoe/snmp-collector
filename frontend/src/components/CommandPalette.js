import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import { searchDevices } from '../services/api';
import { useSignOut } from '../hooks/useSignOut';
import { visibleSections } from '../navConfig';
import { filterItems } from '../utils/commandSearch';
import Icon from './Icon';

const IS_MAC = typeof navigator !== 'undefined' && /mac/i.test(navigator.platform || '');
const SHORTCUT_LABEL = IS_MAC ? '⌘K' : 'Ctrl K';
const SEARCH_DEBOUNCE_MS = 150;
const DEVICE_RESULTS = 8;

// No provider (e.g. a bare Sidebar in a test) -> the trigger just does nothing.
const PaletteContext = createContext({ open: () => {}, shortcutLabel: SHORTCUT_LABEL });
export const useCommandPalette = () => useContext(PaletteContext);

function isTypingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

const hasOpenModal = () =>
  !!document.querySelector('.modal-overlay, [role="dialog"][aria-modal="true"]');

export function CommandPaletteProvider({ children }) {
  const { token } = useAuth();
  const enabled = !!token; // AppShell renders briefly before PrivateRoute redirects
  const [isOpen, setIsOpen] = useState(false);
  const open = useCallback(() => {
    if (!hasOpenModal()) setIsOpen(true);
  }, []);
  const close = useCallback(() => setIsOpen(false), []);

  useEffect(() => {
    if (!enabled) return undefined;
    const onKey = (e) => {
      const isK = (e.metaKey || e.ctrlKey) && e.key?.toLowerCase() === 'k';
      const isSlash = e.key === '/' && !e.metaKey && !e.ctrlKey && !isTypingTarget(e.target);
      if (!isK && !isSlash) return;
      if (isOpen) {
        if (isK) {
          e.preventDefault();
          setIsOpen(false);
        }
        return;
      }
      // Never stack over another dialog (an open edit form would be lost on navigate).
      if (hasOpenModal()) return;
      e.preventDefault();
      setIsOpen(true);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled, isOpen]);

  const value = useMemo(() => ({ open, shortcutLabel: SHORTCUT_LABEL }), [open]);
  return (
    <PaletteContext.Provider value={value}>
      {children}
      {enabled && isOpen && <Palette onClose={close} />}
    </PaletteContext.Provider>
  );
}

function Palette({ onClose }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const signOut = useSignOut();
  const { theme, cycle: cycleTheme } = useTheme();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [devices, setDevices] = useState({ status: 'idle', items: [], total: 0 });
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const returnFocusTo = useRef(document.activeElement);

  useEffect(() => {
    inputRef.current?.focus();
    const target = returnFocusTo.current;
    return () => target?.focus?.();
  }, []);

  // Debounced server-side device search; stale responses are dropped.
  useEffect(() => {
    const term = query.trim();
    if (!term) {
      setDevices({ status: 'idle', items: [], total: 0 });
      return undefined;
    }
    const controller = new AbortController();
    // Drop the previous query's rows: they must not stay selectable under new text.
    setDevices({ status: 'loading', items: [], total: 0 });
    const timer = setTimeout(async () => {
      try {
        const res = await searchDevices(term, { limit: DEVICE_RESULTS, signal: controller.signal });
        if (!controller.signal.aborted) setDevices({ status: 'ok', ...res });
      } catch (err) {
        if (!controller.signal.aborted) setDevices({ status: 'error', items: [], total: 0 });
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const execute = useCallback(
    (item) => {
      onClose();
      if (item.action === 'theme') cycleTheme();
      else if (item.action === 'signout') signOut();
      else if (item.to) navigate(item.to);
    },
    [onClose, cycleTheme, signOut, navigate],
  );

  // Items are plain data (`to` / `action`); behaviour is resolved at selection
  // time, so this list doesn't rebuild when callbacks change.
  const staticItems = useMemo(() => {
    const pages = visibleSections(user?.role).flatMap((section) =>
      section.items.map((i) => ({
        id: `page:${i.to}`,
        group: 'Pages',
        label: i.label,
        keywords: `${section.label} ${i.keywords || ''}`,
        icon: i.icon,
        hint: section.label,
        to: i.to,
      })),
    );
    const actions = [
      {
        id: 'action:theme',
        group: 'Actions',
        label: 'Switch theme',
        keywords: 'dark light mode appearance',
        icon: 'sun',
        action: 'theme',
      },
      {
        id: 'action:password',
        group: 'Actions',
        label: 'Change password',
        keywords: 'account security',
        icon: 'key',
        to: '/change-password',
      },
      {
        id: 'action:logout',
        group: 'Actions',
        label: 'Sign out',
        keywords: 'logout',
        icon: 'logout',
        action: 'signout',
      },
    ];
    return { pages, actions };
  }, [user?.role]);

  const results = useMemo(() => {
    const term = query.trim();
    const deviceRows = devices.items.map((d) => ({
      id: `device:${d.id}`,
      group: 'Devices',
      label: d.name,
      hint: d.ip_address,
      icon: 'devices',
      disabled: !d.enabled,
      to: d.enabled ? `/metrics?device_id=${d.id}` : `/devices?q=${encodeURIComponent(d.name)}`,
    }));
    if (devices.total > devices.items.length) {
      deviceRows.push({
        id: 'device:all',
        group: 'Devices',
        label: `Show all ${devices.total.toLocaleString()} matching devices`,
        icon: 'search',
        to: `/devices?q=${encodeURIComponent(term)}`,
      });
    }
    return [
      ...filterItems(staticItems.pages, term),
      ...(term ? deviceRows : []),
      ...filterItems(staticItems.actions, term),
    ];
  }, [query, devices, staticItems]);

  // Reset on a new query only. Async device results changing the list length must
  // not yank the highlight; clamp instead.
  useEffect(() => setActive(0), [query]);
  const current = results.length ? Math.min(active, results.length - 1) : 0;
  const hintFor = (r) => (r.action === 'theme' ? `Now: ${theme}` : r.hint);

  useEffect(() => {
    listRef.current
      ?.querySelector('[aria-selected="true"]')
      ?.scrollIntoView?.({ block: 'nearest' });
  }, [current, results]);

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (results.length === 0) return;
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => (Math.min(i, results.length - 1) + step + results.length) % results.length);
    } else if (e.key === 'Enter') {
      if (e.nativeEvent?.isComposing) return; // confirming an IME composition, not selecting
      e.preventDefault();
      if (results[current]) execute(results[current]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'Tab') {
      e.preventDefault(); // single-control dialog: keep focus on the input
    }
  };

  let lastGroup = null;
  const term = query.trim();
  const deviceNote =
    term && devices.status === 'loading' && devices.items.length === 0
      ? 'Searching devices…'
      : devices.status === 'error'
        ? 'Device search unavailable'
        : null;

  return (
    <div className="palette-overlay" onMouseDown={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="palette-input-row">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            className="palette-input"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={results.length ? `palette-opt-${current}` : undefined}
            aria-autocomplete="list"
            placeholder="Search devices, jump to a page, run an action…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            spellCheck={false}
            autoComplete="off"
          />
          <kbd className="kbd">esc</kbd>
        </div>

        <ul className="palette-list" id="palette-list" role="listbox" ref={listRef}>
          {results.map((r, i) => {
            const header = r.group !== lastGroup ? r.group : null;
            lastGroup = r.group;
            return (
              <React.Fragment key={r.id}>
                {header && (
                  <li className="palette-group" role="presentation">
                    {header}
                  </li>
                )}
                <li
                  id={`palette-opt-${i}`}
                  role="option"
                  aria-selected={i === current}
                  className={`palette-item${i === current ? ' active' : ''}`}
                  onMouseMove={() => setActive(i)}
                  onClick={() => execute(r)}
                >
                  <Icon name={r.icon} size={15} />
                  <span className="palette-item-label">{r.label}</span>
                  {r.disabled && <span className="badge badge-danger">disabled</span>}
                  {hintFor(r) && <span className="palette-item-hint">{hintFor(r)}</span>}
                </li>
              </React.Fragment>
            );
          })}
          {deviceNote && (
            <li className="palette-note" role="presentation">
              {deviceNote}
            </li>
          )}
          {term && results.length === 0 && !deviceNote && (
            <li className="palette-note" role="presentation">
              No results for “{term}”
            </li>
          )}
        </ul>

        <div className="palette-footer">
          <span>
            <kbd className="kbd">↑</kbd> <kbd className="kbd">↓</kbd> navigate
          </span>
          <span>
            <kbd className="kbd">↵</kbd> select
          </span>
          {!term && (
            <span className="palette-footer-tip">Type to search devices by name or IP</span>
          )}
        </div>
      </div>
    </div>
  );
}
