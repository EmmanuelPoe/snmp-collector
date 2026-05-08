# Enterprise Frontend Redesign
**Date:** 2026-05-08
**Scope:** Full UI overhaul of the React frontend for enterprise-grade quality
**Aesthetic:** Graphite Amber — zinc-black base, amber/gold accent, IBM Plex fonts

---

## Goals

Transform the current development-quality frontend into a polished enterprise monitoring tool by:
1. Replacing the top nav with a left sidebar (enterprise standard layout)
2. Applying a cohesive Graphite Amber design system (new fonts, colors, CSS)
3. Redesigning the login page to match the design system
4. Upgrading the dashboard with charts and a live events feed
5. Fixing all broken CSS classes, inline styles, and nav active state
6. Adding search/filter to device and agent tables
7. Adding a toast notification system

Out of scope: TypeScript migration, component library adoption, mobile responsive nav hamburger menu, user management UI.

---

## Section 1: Design System

### Typography

Replace Inter / system font stack with:
- **Body:** `IBM Plex Sans` (weights: 300, 400, 500, 600, 700)
- **Monospace / labels / numbers:** `IBM Plex Mono` (weights: 400, 500, 600)

Load via Google Fonts in `public/index.html`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

### Color Tokens (CSS custom properties)

Replace the existing color tokens in `index.css` with:

```css
--color-bg-base:        #0d0d10;   /* page background */
--color-bg-surface:     #111113;   /* sidebar, cards */
--color-bg-elevated:    #18181b;   /* modals, dropdowns */
--color-bg-hover:       rgba(255,255,255,0.03);
--color-border:         #1f1f24;   /* primary border */
--color-border-subtle:  #161619;   /* dividers */

--color-accent:         #fbbf24;   /* amber — primary accent */
--color-accent-dim:     rgba(251,191,36,0.08);
--color-accent-border:  rgba(251,191,36,0.2);

--color-success:        #4ade80;
--color-success-dim:    rgba(74,222,128,0.08);
--color-warning:        #fb923c;
--color-warning-dim:    rgba(251,146,60,0.08);
--color-error:          #f87171;
--color-error-dim:      rgba(248,113,113,0.08);
--color-info:           #60a5fa;

--color-text-primary:   #f4f4f5;
--color-text-secondary: #a1a1aa;
--color-text-muted:     #52525b;
--color-text-faint:     #3f3f46;

--font-sans:  'IBM Plex Sans', system-ui, sans-serif;
--font-mono:  'IBM Plex Mono', 'Fira Code', monospace;
```

### Removed tokens

Remove `--color-accent-secondary`, `--color-accent-gradient`, `--color-glass`, `--shadow-glow`. Remove all `backdrop-filter: blur()` glass effects — replace with flat surfaces using `--color-bg-surface`.

### Missing CSS classes to add

Define these classes that are currently referenced but missing:
- `.btn-warning` — amber background, matching `.btn-danger` pattern
- `.alert`, `.alert-danger`, `.alert-warning`, `.alert-info` — banner-style alerts with left border accent
- `.table` — alias for `.data-table` (same styles, both selectors)

### Fix broken patterns

- `.glass-card` → rename to `.card` throughout. Remove backdrop-filter. Use flat `--color-bg-surface` background.
- Remove all `style={{...}}` inline styles from components (device list header, YAML editor, user email in nav, modal buttons). Replace with CSS classes.

---

## Section 2: Layout — Left Sidebar

### New file: `src/components/Sidebar.js`

Replace `NavBar.js` with a `Sidebar.js` component. The sidebar is the primary navigation and is always visible.

**Structure:**
```
sidebar
├── brand block
│   ├── "⬡ SNMP MONITOR" (IBM Plex Mono, amber)
│   └── static sub-label: "infrastructure" (hardcoded, no version endpoint)
├── nav section: Monitor
│   ├── Dashboard
│   ├── Devices
│   ├── Metrics
│   └── Agents
├── nav section: Manage
│   └── Configuration
└── footer
    ├── user email + role badge
    └── Logout button
```

Use React Router `NavLink` (not `Link`) for all nav items so `.active` class applies automatically.

**Width:** 220px fixed, not collapsible (out of scope).

**Active state:** amber left border + amber text + subtle amber background tint. Exactly as shown in the mockup.

### App layout change

`App.js` layout changes from:
```
<NavBar />
<main className="container">...</main>
```
to:
```
<div className="app-shell">
  <Sidebar />
  <div className="app-main">
    <div className="page-content">...</div>
  </div>
</div>
```

CSS for `app-shell`: `display: flex; height: 100vh; overflow: hidden;`
CSS for `app-main`: `flex: 1; display: flex; flex-direction: column; overflow: hidden;`
CSS for `page-content`: `flex: 1; overflow-y: auto; padding: 20px 24px;`

Remove `.container` max-width wrapper — pages now fill the available width naturally.

### Topbar per page

Each page renders its own `<div className="page-header">` with the page title and any page-level actions (e.g., "+ Add Device" button). This replaces the current inline-styled header rows.

```css
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}
```

---

## Section 3: Login Page Redesign

### Current state
The login page uses browser-default styles and raw inline CSS. It is completely disconnected from the design system.

### New design

Full-viewport two-panel layout:
- **Left panel (40%):** brand panel — dark zinc background, amber logo, product name, tagline ("Infrastructure visibility at scale."), subtle grid/pattern background.
- **Right panel (60%):** form panel — slightly lighter surface, centered form card.

Form card contains:
- "Sign in" heading (IBM Plex Sans, 20px, semibold)
- Email input (`.input` class)
- Password input (`.input` class)
- "Sign in" submit button (`.btn .btn-primary`)
- Error message area (`.alert .alert-danger`) — only shown on failed login

No registration link (admin creates users via API only — already specified in auth design).

**CSS:** No inline styles. All styling via classes defined in `index.css`.

---

## Section 4: Dashboard Redesign

### Current state
4 stat cards + a raw metric rows table. No trend data. No charts.

### New layout

```
page-header: "Dashboard" + LIVE badge + last-updated timestamp

row 1: 4 stat cards (grid, equal width)
  - Total Devices     (amber number)
  - Active Devices    (green number)
  - Agents Online     (white "3 / 3" format)
  - Polls / min       (violet number)

row 2: 2-column chart row
  - left (2/3): "Network Traffic · Last 24h" — AreaChart (In/Out octets, amber + gray lines)
  - right (1/3): "Device Status" — BarChart showing Active / Disabled / Total device counts

row 3: 2-column detail row
  - left: "Agent Status" — list of agents with hostname, device count, status pill
  - right: "Recent Events" — timestamped event log (last 5 events)
```

**Data sources:**
- Stat cards: existing `/api/devices` and `/api/agents` calls already in the app
- Traffic chart: existing metrics API (`/api/metrics`) — fetch `ifInOctets` + `ifOutOctets` summed across all devices, last 24h
- Device Status chart: derived from existing `/api/devices` response — count enabled vs disabled
- Agent Status: existing `/api/agents` call
- Recent Events: client-side log of state changes observed during the session (agent status changes, device adds); not persisted to backend

**Chart library:** Recharts (already installed). Use `AreaChart` for traffic, `LineChart` for success rate.

**LIVE badge:** Amber pill with pulsing dot. Dashboard auto-refreshes every 30s (matches existing agents page behavior).

### Remove
Remove the "Recent Metrics" raw data table from the dashboard. That data is better explored on the Metrics page.

---

## Section 5: Table Improvements

### Search / filter

Add a search input above the Devices and Agents tables:
- Devices: filter by name or IP address (client-side, no API change)
- Agents: filter by hostname or IP (client-side)

The input uses `.input` class, placed in the page-header row (right side, opposite the page title).

### Sortable columns

Devices table: clicking column headers for Name, IP Address, Status sorts ascending/descending. Visual indicator: `↑` / `↓` appended to active sort column header.

Agents table: same, for Hostname and Status columns.

Implementation: `useState` for `{column, direction}` sort state; sort applied to the displayed array before render. No API changes.

### `.table` fix

`ConfigurationManager` uses `.table` class. Add `.table` as an alias for `.data-table` in `index.css`.

---

## Section 6: Toast Notification System

### Current state
No feedback on create/edit/delete/save operations.

### New implementation

**New file:** `src/components/Toast.js` + `src/hooks/useToast.js`

A stack of up to 4 toast notifications in the top-right corner. Each toast:
- Auto-dismisses after 4 seconds
- Has a type: `success` | `error` | `warning` | `info`
- Shows a colored left border and icon matching the type
- Can be manually dismissed with an ✕ button
- Stacks vertically with gap, newest on top

**Integration:**
- `ToastContainer` rendered once in `App.js` (outside routing, always visible)
- `useToast()` hook returns `{ showToast }` — call `showToast('message', 'success')` from any component
- Replace all `alert()` calls and silent failures with `showToast()`
- Add success toasts to: device create/edit/delete, config save, schedule update

**CSS:** Fixed position `top: 20px; right: 20px; z-index: 1000`. Each toast slides in from the right (CSS `@keyframes slideIn`).

---

## Section 7: Configuration Page Fixes

### Inline styles to remove
- YAML `<textarea>` uses `style={{fontFamily: 'Fira Code'...}}` → replace with `.code-editor` class using `--font-mono`
- `.btn-warning` on "Reload SNMP Exporter Service" → define this class in `index.css`

### `.btn-warning` definition
```css
.btn-warning {
  background: var(--color-warning);
  color: #000;
  border: none;
}
.btn-warning:hover { filter: brightness(1.1); }
```

---

## File Changes Summary

### New files
- `src/components/Sidebar.js` — left nav, replaces NavBar
- `src/components/Toast.js` — toast container + individual toast
- `src/hooks/useToast.js` — toast state management hook

### Modified files
- `public/index.html` — add Google Fonts link tags
- `src/index.css` — new color tokens, typography, `.card`, `.btn-warning`, `.alert`, `.table`, `.page-header`, `.app-shell`, sidebar CSS, toast CSS, login page CSS
- `src/App.css` — remove glass card styles; update layout to app-shell
- `src/App.js` — swap NavBar → Sidebar; add app-shell wrapper; add ToastContainer
- `src/pages/LoginPage.js` — full redesign, no inline styles
- `src/pages/Dashboard.js` — new layout with charts, agent list, events feed
- `src/pages/DeviceManagement.js` — add search input, sortable columns, remove inline styles
- `src/pages/AgentsPage.js` — add search input, sortable columns, fix `.alert-danger`
- `src/pages/ConfigurationManager.js` — fix `.table` → `.data-table`, remove textarea inline styles, add `.btn-warning`
- `src/pages/MetricsViewer.js` — CSS class names updated (`.glass-card` → `.card`); no structural changes

### Deleted files
- `src/components/NavBar.js` — replaced by Sidebar

### Files intentionally not touched
- All backend files
- `src/services/api.js` — no changes needed

---

## Implementation Order

1. **Design system** — update `index.css` color tokens, typography, add missing classes, remove glass styles
2. **Sidebar** — build `Sidebar.js`, update `App.js` layout, delete `NavBar.js`
3. **Login page** — full redesign
4. **Dashboard** — new layout with charts and data
5. **Toast system** — build hook + component, wire into device/config operations
6. **Table improvements** — search + sort on Devices and Agents
7. **Config page fixes** — inline styles, `.btn-warning`
