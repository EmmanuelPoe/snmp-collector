# Enterprise Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the React frontend with Graphite Amber aesthetics, left sidebar nav, redesigned login/dashboard, toast notifications, and table search/sort.

**Architecture:** Replace top navbar with a persistent 220px left sidebar using NavLink for active state. New color tokens and IBM Plex fonts replace the current cyan/zinc palette. Toast state lives in React Context so any component can trigger notifications without prop drilling.

**Tech Stack:** React 18, React Router v6 (NavLink), Recharts (already installed), IBM Plex Sans + IBM Plex Mono (Google Fonts), CSS custom properties.

---

## File Map

**New files:**
- `src/components/Sidebar.js` — left nav, replaces inline NavBar in App.js
- `src/hooks/useToast.js` — toast context + hook
- `src/components/ToastContainer.js` — renders toast stack

**Modified files:**
- `public/index.html` — add IBM Plex Sans font
- `src/index.css` — replace all design tokens, add new component classes
- `src/App.css` — replace navbar/layout with sidebar/app-shell styles
- `src/App.js` — swap NavBar → Sidebar, add ToastProvider, app-shell wrapper
- `src/pages/LoginPage.js` — full redesign, no inline styles
- `src/components/Dashboard.js` — new layout with charts, agent list, events
- `src/components/DeviceManagement.js` — search, sort, remove inline styles, toast
- `src/components/AgentsPage.js` — search, sort, fix .alert-danger, toast
- `src/components/ConfigurationManager.js` — remove inline styles, .code-editor, toast
- `src/components/MetricsViewer.js` — replace glass-card → card

**No changes:** `src/services/api.js`, `src/hooks/useAuth.js`, `src/components/PrivateRoute.js`

---

## Task 1: Design System — CSS Tokens, Typography, New Classes

**Files:**
- Modify: `public/index.html`
- Modify: `src/index.css`
- Modify: `src/App.css`

- [ ] **Step 1: Add IBM Plex Sans to public/index.html**

Replace the existing font link (which has Barlow/IBM Plex Mono) with one that also includes IBM Plex Sans:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#0d0d10" />
    <meta name="description" content="SNMP Metrics Collector - Monitor and manage network device metrics" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <title>SNMP Monitor</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
```

- [ ] **Step 2: Replace src/index.css entirely**

```css
:root {
  --color-bg-base:        #0d0d10;
  --color-bg-surface:     #111113;
  --color-bg-elevated:    #18181b;
  --color-bg-hover:       rgba(255,255,255,0.03);
  --color-border:         #1f1f24;
  --color-border-subtle:  #161619;

  --color-accent:         #fbbf24;
  --color-accent-dim:     rgba(251,191,36,0.08);
  --color-accent-border:  rgba(251,191,36,0.2);

  --color-success:        #4ade80;
  --color-success-dim:    rgba(74,222,128,0.08);
  --color-success-border: rgba(74,222,128,0.2);
  --color-warning:        #fb923c;
  --color-warning-dim:    rgba(251,146,60,0.08);
  --color-warning-border: rgba(251,146,60,0.2);
  --color-error:          #f87171;
  --color-error-dim:      rgba(248,113,113,0.08);
  --color-error-border:   rgba(248,113,113,0.2);
  --color-info:           #60a5fa;
  --color-info-dim:       rgba(96,165,250,0.08);
  --color-info-border:    rgba(96,165,250,0.2);

  --color-text-primary:   #f4f4f5;
  --color-text-secondary: #a1a1aa;
  --color-text-muted:     #52525b;
  --color-text-faint:     #3f3f46;

  --font-sans: 'IBM Plex Sans', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', 'Fira Code', monospace;

  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;
  --spacing-2xl: 3rem;

  --radius-sm: 3px;
  --radius-md: 4px;
  --radius-lg: 6px;

  --shadow-sm: 0 1px 2px rgba(0,0,0,0.4);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.5);
  --shadow-lg: 0 10px 20px rgba(0,0,0,0.6);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #root { height: 100%; }

body {
  font-family: var(--font-sans);
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 14px;
}

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  line-height: 1.2;
  color: var(--color-text-primary);
}
h1 { font-size: 1.5rem; }
h2 { font-size: 1.25rem; }
h3 { font-size: 1.125rem; }

/* ── Card ── */
.card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

/* ── Buttons ── */
.btn {
  padding: 0.4rem 0.875rem;
  border-radius: var(--radius-md);
  border: none;
  font-family: var(--font-sans);
  font-weight: 500;
  font-size: 0.8125rem;
  cursor: pointer;
  transition: filter 0.15s, opacity 0.15s;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  white-space: nowrap;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-primary {
  background: var(--color-accent);
  color: #000;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.1); }

.btn-secondary {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}
.btn-secondary:hover:not(:disabled) { color: var(--color-text-primary); border-color: #3f3f46; }

.btn-success {
  background: var(--color-success);
  color: #000;
}
.btn-success:hover:not(:disabled) { filter: brightness(1.1); }

.btn-danger {
  background: var(--color-error);
  color: #fff;
}
.btn-danger:hover:not(:disabled) { filter: brightness(1.1); }

.btn-warning {
  background: var(--color-warning);
  color: #000;
}
.btn-warning:hover:not(:disabled) { filter: brightness(1.1); }

.btn-sm {
  padding: 0.2rem 0.6rem;
  font-size: 0.75rem;
}

/* ── Inputs ── */
.input, .select {
  width: 100%;
  padding: 0.4rem 0.75rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input:focus, .select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-dim);
}
.input::placeholder { color: var(--color-text-faint); }

.code-editor {
  width: 100%;
  min-height: 350px;
  padding: 1rem;
  background: #0a0a0d;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  resize: vertical;
}
.code-editor:focus {
  outline: none;
  border-color: var(--color-accent);
}

/* ── Badges ── */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid transparent;
}
.badge-success { color: var(--color-success); background: var(--color-success-dim); border-color: var(--color-success-border); }
.badge-danger  { color: var(--color-error);   background: var(--color-error-dim);   border-color: var(--color-error-border); }
.badge-warning { color: var(--color-warning); background: var(--color-warning-dim); border-color: var(--color-warning-border); }
.badge-info    { color: var(--color-info);    background: var(--color-info-dim);    border-color: var(--color-info-border); }

/* ── Alerts ── */
.alert {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  border-left: 3px solid;
  font-size: 0.875rem;
  margin-bottom: var(--spacing-md);
}
.alert-danger  { background: var(--color-error-dim);   border-color: var(--color-error);   color: var(--color-error); }
.alert-warning { background: var(--color-warning-dim); border-color: var(--color-warning); color: var(--color-warning); }
.alert-info    { background: var(--color-info-dim);    border-color: var(--color-info);    color: var(--color-info); }
.alert-success { background: var(--color-success-dim); border-color: var(--color-success); color: var(--color-success); }

/* ── Data Table ── */
.data-table, .table {
  width: 100%;
  border-collapse: collapse;
}
.data-table th, .table th {
  padding: 0.6rem 0.875rem;
  text-align: left;
  background: var(--color-bg-elevated);
  color: var(--color-text-faint);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.data-table th.sortable, .table th.sortable {
  cursor: pointer;
  user-select: none;
}
.data-table th.sortable:hover, .table th.sortable:hover {
  color: var(--color-text-secondary);
}
.data-table td, .table td {
  padding: 0.6rem 0.875rem;
  border-bottom: 1px solid var(--color-border-subtle);
  vertical-align: middle;
}
.data-table tbody tr:last-child td,
.table tbody tr:last-child td {
  border-bottom: none;
}
.data-table tbody tr:hover, .table tbody tr:hover {
  background: var(--color-bg-hover);
}

/* ── Form ── */
.form-group { margin-bottom: var(--spacing-md); }
.form-label {
  display: block;
  margin-bottom: 0.3rem;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-weight: 500;
}
.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing-md);
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  animation: fadeIn 0.15s ease-out;
}
.modal {
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  max-width: 580px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
}
.modal-header h3 { margin: 0; }
.modal-close {
  background: none;
  border: none;
  color: var(--color-text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  line-height: 1;
  padding: 0.2rem;
}
.modal-close:hover { color: var(--color-text-primary); }

.action-buttons {
  display: flex;
  gap: var(--spacing-sm);
  justify-content: flex-end;
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border);
}

/* ── Spinner ── */
.spinner {
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  animation: spin 0.7s linear infinite;
}
.loading-center {
  display: flex;
  justify-content: center;
  padding: 4rem;
}

/* ── Utility ── */
.text-muted  { color: var(--color-text-muted); }
.text-faint  { color: var(--color-text-faint); }
.text-sm     { font-size: 0.8125rem; }
.text-xs     { font-size: 0.75rem; }
.font-mono   { font-family: var(--font-mono); }
.text-accent { color: var(--color-accent); }
.text-success { color: var(--color-success); }
.text-error   { color: var(--color-error); }

/* ── Animations ── */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes slideInRight {
  from { opacity: 0; transform: translateX(20px); }
  to   { opacity: 1; transform: translateX(0); }
}

.fade-in { animation: fadeIn 0.25s ease-out; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
```

- [ ] **Step 3: Replace src/App.css entirely**

```css
/* ── App Shell (sidebar layout) ── */
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg-base);
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* ── Sidebar ── */
.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--color-bg-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-brand {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.sidebar-brand-name {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-accent);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.sidebar-brand-sub {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-faint);
  margin-top: 3px;
}

.sidebar-section-label {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-text-faint);
  padding: 14px 16px 4px;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 16px;
  color: var(--color-text-muted);
  text-decoration: none;
  font-size: 13px;
  border-left: 2px solid transparent;
  transition: color 0.12s, background 0.12s;
}
.nav-item:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}
.nav-item.active {
  color: var(--color-accent);
  background: var(--color-accent-dim);
  border-left-color: var(--color-accent);
}
.nav-icon {
  font-size: 13px;
  width: 16px;
  text-align: center;
  flex-shrink: 0;
}

.sidebar-footer {
  border-top: 1px solid var(--color-border);
  padding: 12px 16px;
  flex-shrink: 0;
}
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.user-online-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  flex-shrink: 0;
}
.sidebar-user-email {
  font-size: 11px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-user-role {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-faint);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 1px;
}
.sidebar-logout {
  width: 100%;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-faint);
  font-family: var(--font-sans);
  font-size: 11px;
  padding: 5px 8px;
  cursor: pointer;
  text-align: left;
  transition: color 0.12s, border-color 0.12s;
}
.sidebar-logout:hover {
  color: var(--color-error);
  border-color: var(--color-error-border);
}

/* ── Page Header ── */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.page-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.page-subtitle {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

/* ── Live Badge ── */
.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-accent);
  background: var(--color-accent-dim);
  border: 1px solid var(--color-accent-border);
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.06em;
}
.live-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* ── Stats Row ── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.stat-label {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
  margin-bottom: 6px;
}
.stat-value {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 600;
  line-height: 1;
  color: var(--color-accent);
}
.stat-value.green  { color: var(--color-success); }
.stat-value.white  { color: var(--color-text-primary); }
.stat-value.violet { color: #a78bfa; }
.stat-sub {
  font-size: 11px;
  color: var(--color-text-faint);
  margin-top: 6px;
}
.stat-delta-up { color: var(--color-success); }

/* ── Dashboard charts row ── */
.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.detail-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.chart-title {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
  margin-bottom: 12px;
}
.chart-legend {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: var(--color-text-muted);
}
.legend-line {
  display: inline-block;
  width: 10px;
  height: 2px;
  border-radius: 1px;
  vertical-align: middle;
  margin-right: 4px;
}

/* ── Agent status list ── */
.agent-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-subtle);
}
.agent-row:last-child { border-bottom: none; }
.agent-name {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-text-secondary);
}
.agent-meta {
  font-size: 10px;
  color: var(--color-text-faint);
  margin-top: 1px;
}

/* ── Events feed ── */
.event-row {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-subtle);
  align-items: baseline;
}
.event-row:last-child { border-bottom: none; }
.event-time {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--color-text-faint);
  flex-shrink: 0;
  width: 44px;
}
.event-text {
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.4;
}
.event-text strong { color: var(--color-text-secondary); font-weight: 500; }

/* ── Table search/controls ── */
.table-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 12px;
}
.table-search {
  max-width: 260px;
}

/* ── Login page ── */
.login-shell {
  display: flex;
  height: 100vh;
}
.login-brand-panel {
  width: 40%;
  background: var(--color-bg-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  position: relative;
  overflow: hidden;
}
.login-brand-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--color-border) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-border) 1px, transparent 1px);
  background-size: 40px 40px;
  opacity: 0.4;
}
.login-brand-content { position: relative; text-align: center; }
.login-brand-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
  color: var(--color-accent);
}
.login-brand-name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-accent);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 0.5rem;
}
.login-brand-tagline {
  font-size: 13px;
  color: var(--color-text-faint);
  max-width: 220px;
  line-height: 1.5;
}
.login-form-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: var(--color-bg-base);
}
.login-form-card {
  width: 100%;
  max-width: 380px;
}
.login-form-card h2 {
  margin-bottom: 0.375rem;
}
.login-form-subtext {
  font-size: 12px;
  color: var(--color-text-faint);
  margin-bottom: 1.75rem;
}
.login-field {
  margin-bottom: 1rem;
}
.login-submit {
  width: 100%;
  padding: 0.6rem;
  margin-top: 0.5rem;
  font-size: 0.875rem;
}

/* ── Toast container ── */
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: all;
  min-width: 280px;
  max-width: 380px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  border-left: 3px solid;
  padding: 10px 12px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  box-shadow: var(--shadow-lg);
  animation: slideInRight 0.2s ease-out;
  font-size: 13px;
}
.toast-success { border-left-color: var(--color-success); }
.toast-error   { border-left-color: var(--color-error); }
.toast-warning { border-left-color: var(--color-warning); }
.toast-info    { border-left-color: var(--color-info); }
.toast-message { flex: 1; color: var(--color-text-secondary); line-height: 1.4; }
.toast-dismiss {
  background: none;
  border: none;
  color: var(--color-text-faint);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
  flex-shrink: 0;
}
.toast-dismiss:hover { color: var(--color-text-primary); }
```

- [ ] **Step 4: Verify the app still loads**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector/frontend && npm start
```

Open http://localhost:3000 — expect the login page to appear (still unstyled for now — that's fine, Task 3 fixes it). The app should not crash. Check the browser console for no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/public/index.html frontend/src/index.css frontend/src/App.css
git commit -m "feat(frontend): replace design system with Graphite Amber tokens and CSS"
```

---

## Task 2: Sidebar + App Shell

**Files:**
- Create: `src/components/Sidebar.js`
- Modify: `src/App.js`

- [ ] **Step 1: Create src/components/Sidebar.js**

```jsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const NAV_SECTIONS = [
  {
    label: 'Monitor',
    items: [
      { to: '/',        icon: '◈', label: 'Dashboard' },
      { to: '/devices', icon: '◻', label: 'Devices' },
      { to: '/metrics', icon: '▦', label: 'Metrics' },
      { to: '/agents',  icon: '◎', label: 'Agents' },
    ],
  },
  {
    label: 'Manage',
    items: [
      { to: '/config', icon: '⊞', label: 'Configuration' },
    ],
  },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">⬡ SNMP Monitor</div>
        <div className="sidebar-brand-sub">infrastructure</div>
      </div>

      <nav className="sidebar-nav">
        {NAV_SECTIONS.map(section => (
          <div key={section.label}>
            <div className="sidebar-section-label">{section.label}</div>
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        {user && (
          <div className="sidebar-user">
            <div className="user-online-dot" />
            <div>
              <div className="sidebar-user-email">{user.email}</div>
              <div className="sidebar-user-role">{user.role || 'user'}</div>
            </div>
          </div>
        )}
        <button className="sidebar-logout" onClick={handleLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Replace src/App.js**

```jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DeviceManagement from './components/DeviceManagement';
import MetricsViewer from './components/MetricsViewer';
import ConfigurationManager from './components/ConfigurationManager';
import AgentsPage from './components/AgentsPage';
import LoginPage from './pages/LoginPage';
import PrivateRoute from './components/PrivateRoute';
import Sidebar from './components/Sidebar';
import { ToastProvider } from './hooks/useToast';
import './App.css';

function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <div className="page-content">
          <Routes>
            <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/devices" element={<PrivateRoute><DeviceManagement /></PrivateRoute>} />
            <Route path="/metrics" element={<PrivateRoute><MetricsViewer /></PrivateRoute>} />
            <Route path="/agents" element={<PrivateRoute><AgentsPage /></PrivateRoute>} />
            <Route path="/config" element={<PrivateRoute><ConfigurationManager /></PrivateRoute>} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </Router>
    </ToastProvider>
  );
}
```

Note: `ToastProvider` is imported from `./hooks/useToast` — this will be created in Task 5. The app will fail to compile until Task 5 is done. To avoid breakage, create a temporary stub now:

- [ ] **Step 3: Create stub src/hooks/useToast.js (replaced fully in Task 5)**

```js
import React, { createContext, useContext } from 'react';

const ToastContext = createContext({ showToast: () => {} });

export function ToastProvider({ children }) {
  return <ToastContext.Provider value={{ showToast: () => {} }}>{children}</ToastContext.Provider>;
}

export function useToast() {
  return useContext(ToastContext);
}
```

- [ ] **Step 4: Verify sidebar renders**

```bash
# frontend dev server should still be running from Task 1
```

Open http://localhost:3000/login — you should be redirected to login (PrivateRoute). After logging in, you should see:
- Left sidebar 220px wide with "⬡ SNMP MONITOR" brand and nav items
- Active page highlighted in amber with left border
- User email and "Sign out" button in footer
- Dashboard content fills the right area

Click each nav item and verify the active state updates.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.js frontend/src/App.js frontend/src/hooks/useToast.js
git commit -m "feat(frontend): add left sidebar nav, app-shell layout, replace top navbar"
```

---

## Task 3: Login Page Redesign

**Files:**
- Modify: `src/pages/LoginPage.js`

- [ ] **Step 1: Replace src/pages/LoginPage.js**

```jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    const body = new URLSearchParams({ username: email, password });
    try {
      const resp = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });
      if (!resp.ok) {
        setError('Invalid email or password.');
        return;
      }
      const data = await resp.json();
      login(data.access_token);
      navigate('/');
    } catch {
      setError('Network error — is the backend running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-brand-panel">
        <div className="login-brand-content">
          <div className="login-brand-icon">⬡</div>
          <div className="login-brand-name">SNMP Monitor</div>
          <div className="login-brand-tagline">Infrastructure visibility at scale.</div>
        </div>
      </div>

      <div className="login-form-panel">
        <div className="login-form-card">
          <h2>Sign in</h2>
          <p className="login-form-subtext">Enter your credentials to access the dashboard.</p>

          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="login-field">
              <label className="form-label">Email</label>
              <input
                className="input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="admin@localhost"
                autoComplete="email"
                autoFocus
              />
            </div>

            <div className="login-field">
              <label className="form-label">Password</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary login-submit"
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify login page looks correct**

Open http://localhost:3000/login (log out first if needed). Expect:
- Two-panel layout: dark grid-pattern left panel with amber ⬡ icon and tagline
- Right panel with centered form card
- `.alert.alert-danger` appears styled (amber-left-border red alert) on bad credentials
- Form uses `.input` class styling (dark background, amber focus ring)
- Submit button is amber `.btn-primary`
- No inline styles anywhere

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/LoginPage.js
git commit -m "feat(frontend): redesign login page with two-panel layout"
```

---

## Task 4: Dashboard Redesign

**Files:**
- Modify: `src/components/Dashboard.js`

- [ ] **Step 1: Replace src/components/Dashboard.js**

```jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getDevices, getAgents, getMetrics } from '../services/api';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts';

const STATUS_BADGE = {
  online:   'badge-success',
  degraded: 'badge-warning',
  offline:  'badge-danger',
};

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatBytes(val) {
  if (val == null) return '—';
  if (val > 1e9) return (val / 1e9).toFixed(1) + ' GB';
  if (val > 1e6) return (val / 1e6).toFixed(1) + ' MB';
  if (val > 1e3) return (val / 1e3).toFixed(1) + ' KB';
  return val + ' B';
}

const CHART_TOOLTIP_STYLE = {
  backgroundColor: '#18181b',
  border: '1px solid #1f1f24',
  borderRadius: 4,
  fontSize: 11,
  fontFamily: "'IBM Plex Mono', monospace",
  color: '#a1a1aa',
};

export default function Dashboard() {
  const [devices, setDevices] = useState([]);
  const [agents, setAgents] = useState([]);
  const [trafficData, setTrafficData] = useState([]);
  const [events, setEvents] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [devicesRes, agentsRes, metricsRes] = await Promise.all([
        getDevices(),
        getAgents().catch(() => []),
        getMetrics({ limit: 100 }).catch(() => []),
      ]);
      setDevices(devicesRes);
      setAgents(agentsRes);
      setTrafficData(buildTrafficSeries(metricsRes));
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 30000);
    return () => clearInterval(iv);
  }, [loadData]);

  // Add an event entry when agents change status (simple client-side log)
  useEffect(() => {
    if (agents.length === 0) return;
    const degraded = agents.filter(a => a.status !== 'online');
    if (degraded.length > 0) {
      setEvents(prev => [
        {
          time: new Date(),
          text: `${degraded[0].hostname || degraded[0].agent_id} status: ${degraded[0].status}`,
        },
        ...prev,
      ].slice(0, 8));
    }
  }, [agents]);

  if (loading) {
    return <div className="loading-center"><div className="spinner" /></div>;
  }

  const totalDevices = devices.length;
  const activeDevices = devices.filter(d => d.enabled).length;
  const onlineAgents = agents.filter(a => a.status === 'online').length;

  const deviceStatusData = [
    { label: 'Active', count: activeDevices },
    { label: 'Disabled', count: totalDevices - activeDevices },
  ];

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Dashboard</div>
          {lastUpdated && (
            <div className="page-subtitle">
              updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
          )}
        </div>
        <span className="live-badge"><span className="live-dot" />LIVE</span>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Total Devices</div>
          <div className="stat-value">{totalDevices}</div>
          <div className="stat-sub">{activeDevices} active</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active Devices</div>
          <div className="stat-value green">{activeDevices}</div>
          <div className="stat-sub">{totalDevices - activeDevices} disabled</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Agents Online</div>
          <div className="stat-value white">
            {onlineAgents} <span style={{ fontSize: 13, color: 'var(--color-text-faint)' }}>/ {agents.length}</span>
          </div>
          <div className="stat-sub">
            {onlineAgents === agents.length && agents.length > 0 ? (
              <span className="text-success">all healthy</span>
            ) : agents.length === 0 ? 'none registered' : (
              <span className="text-error">{agents.length - onlineAgents} degraded/offline</span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Recent Polls</div>
          <div className="stat-value violet">{trafficData.length}</div>
          <div className="stat-sub">data points loaded</div>
        </div>
      </div>

      {/* Charts */}
      <div className="charts-row">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="chart-title">Network Traffic · Recent</div>
            <div className="chart-legend">
              <span><span className="legend-line" style={{ background: '#fbbf24' }} />In</span>
              <span><span className="legend-line" style={{ background: '#52525b' }} />Out</span>
            </div>
          </div>
          {trafficData.length > 0 ? (
            <ResponsiveContainer width="100%" height={90}>
              <AreaChart data={trafficData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="inGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f1f24" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#3f3f46', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
                <YAxis hide />
                <Tooltip contentStyle={CHART_TOOLTIP_STYLE} formatter={v => formatBytes(v)} />
                <Area type="monotone" dataKey="inOctets" stroke="#fbbf24" strokeWidth={1.5} fill="url(#inGrad)" dot={false} name="In" />
                <Area type="monotone" dataKey="outOctets" stroke="#52525b" strokeWidth={1.5} fill="none" dot={false} name="Out" strokeDasharray="4 2" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 90, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span className="text-faint text-xs">No traffic data collected yet</span>
            </div>
          )}
        </div>

        <div className="card">
          <div className="chart-title">Device Status</div>
          <ResponsiveContainer width="100%" height={90}>
            <BarChart data={deviceStatusData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f24" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#3f3f46', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <YAxis hide />
              <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
              <Bar dataKey="count" fill="#fbbf24" radius={[2, 2, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detail row */}
      <div className="detail-row">
        <div className="card">
          <div className="chart-title">Agent Status</div>
          {agents.length === 0 ? (
            <p className="text-faint text-xs" style={{ paddingTop: 8 }}>No agents registered.</p>
          ) : (
            agents.map(agent => (
              <div className="agent-row" key={agent.agent_id}>
                <div>
                  <div className="agent-name">{agent.hostname || agent.agent_id}</div>
                  <div className="agent-meta">{agent.ip} · {agent.agent_id?.slice(0, 12)}…</div>
                </div>
                <span className={`badge ${STATUS_BADGE[agent.status] || 'badge-info'}`}>
                  {agent.status}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="card">
          <div className="chart-title">Recent Events</div>
          {events.length === 0 ? (
            <div className="event-row">
              <span className="event-time">{lastUpdated ? formatTime(lastUpdated) : '—'}</span>
              <span className="event-text">System loaded — {totalDevices} devices, {agents.length} agents</span>
            </div>
          ) : (
            events.slice(0, 5).map((ev, i) => (
              <div className="event-row" key={i}>
                <span className="event-time">{formatTime(ev.time)}</span>
                <span className="event-text">{ev.text}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// Build time-series data from raw metrics. Aggregates ifInOctets/ifOutOctets by timestamp bucket.
function buildTrafficSeries(metrics) {
  const inKey = 'ifInOctets';
  const outKey = 'ifOutOctets';

  const buckets = {};
  metrics.forEach(m => {
    if (!m.timestamp) return;
    const ts = new Date(m.timestamp);
    const bucket = `${ts.getHours()}:${String(ts.getMinutes()).padStart(2, '0')}`;
    if (!buckets[bucket]) buckets[bucket] = { time: bucket, inOctets: 0, outOctets: 0 };
    if (m.oid_name === inKey)  buckets[bucket].inOctets  += (m.value || 0);
    if (m.oid_name === outKey) buckets[bucket].outOctets += (m.value || 0);
  });

  return Object.values(buckets).slice(-20);
}
```

- [ ] **Step 2: Verify dashboard**

Open http://localhost:3000. Expect:
- Page header "Dashboard" with LIVE badge and timestamp
- 4 stat cards in a row (amber/green/white/violet numbers)
- Traffic area chart (if metrics exist) or empty-state message
- Device Status bar chart
- Agent Status list on left, Recent Events on right
- Auto-refreshes every 30 seconds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Dashboard.js
git commit -m "feat(frontend): redesign dashboard with charts, agent status, events feed"
```

---

## Task 5: Toast Notification System

**Files:**
- Modify: `src/hooks/useToast.js` (replace the stub from Task 2)
- Create: `src/components/ToastContainer.js`
- Modify: `src/App.js`

- [ ] **Step 1: Replace src/hooks/useToast.js with full implementation**

```js
import React, { createContext, useContext, useState, useCallback } from 'react';
import ToastContainer from '../components/ToastContainer';

const ToastContext = createContext({ showToast: () => {} });

let idCounter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info') => {
    const id = ++idCounter;
    setToasts(prev => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
```

- [ ] **Step 2: Create src/components/ToastContainer.js**

```jsx
import React from 'react';

const ICONS = {
  success: '✓',
  error:   '✕',
  warning: '⚠',
  info:    'ℹ',
};

export default function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span style={{ color: typeColor(toast.type), fontSize: 13, flexShrink: 0 }}>
            {ICONS[toast.type]}
          </span>
          <span className="toast-message">{toast.message}</span>
          <button className="toast-dismiss" onClick={() => onDismiss(toast.id)}>×</button>
        </div>
      ))}
    </div>
  );
}

function typeColor(type) {
  const map = {
    success: 'var(--color-success)',
    error:   'var(--color-error)',
    warning: 'var(--color-warning)',
    info:    'var(--color-info)',
  };
  return map[type] || 'var(--color-text-secondary)';
}
```

- [ ] **Step 3: Verify toasts render**

The `ToastProvider` is already in `App.js` from Task 2 and imports from `./hooks/useToast`. Open the browser console and run:

```js
// In browser console — manually trigger a toast to test rendering
// (This is just a visual check; we'll wire real calls in Task 6)
```

Actually just verify no compile errors and the app loads. The toast container won't show anything until wired in Task 6.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useToast.js frontend/src/components/ToastContainer.js
git commit -m "feat(frontend): add toast notification system"
```

---

## Task 6: Wire Toasts into Device, Config, and Agent Operations

**Files:**
- Modify: `src/components/DeviceManagement.js`
- Modify: `src/components/ConfigurationManager.js`
- Modify: `src/components/AgentsPage.js`

- [ ] **Step 1: Update DeviceManagement.js — remove inline styles, add toasts, replace glass-card**

Replace the full file:

```jsx
import React, { useState, useEffect } from 'react';
import { getDevices, createDevice, updateDevice, deleteDevice, getModules, getAgents } from '../services/api';
import { useToast } from '../hooks/useToast';

export default function DeviceManagement() {
  const { showToast } = useToast();
  const [devices, setDevices] = useState([]);
  const [agents, setAgents] = useState([]);
  const [availableModules, setAvailableModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [formData, setFormData] = useState({
    name: '', ip_address: '', snmp_version: '2c', snmp_community: 'public',
    snmp_port: 161, snmp_modules: ['if_mib'], device_type: 'switch',
    description: '', enabled: true,
    username: '', auth_protocol: 'SHA', auth_password: '',
    priv_protocol: 'AES', priv_password: '', assigned_agent_id: '',
  });

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [devicesData, modulesData, agentsData] = await Promise.all([
        getDevices(),
        getModules(),
        getAgents().catch(() => []),
      ]);
      setDevices(devicesData);
      setAvailableModules(modulesData);
      setAgents(agentsData);
    } catch {
      showToast('Failed to load devices', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...formData };
      if (payload.snmp_version === '2c') {
        payload.username = null; payload.auth_protocol = null;
        payload.auth_password = null; payload.priv_protocol = null; payload.priv_password = null;
      }
      if (!payload.assigned_agent_id) payload.assigned_agent_id = null;
      if (editingDevice) {
        await updateDevice(editingDevice.id, payload);
        showToast(`Device "${payload.name}" updated`, 'success');
      } else {
        await createDevice(payload);
        showToast(`Device "${payload.name}" created`, 'success');
      }
      setShowModal(false);
      resetForm();
      loadData();
    } catch (err) {
      showToast('Error saving device: ' + (err.response?.data?.detail || err.message), 'error');
    }
  };

  const handleEdit = (device) => {
    setEditingDevice(device);
    setFormData({
      name: device.name, ip_address: device.ip_address,
      snmp_version: device.snmp_version, snmp_community: device.snmp_community,
      snmp_port: device.snmp_port, snmp_modules: device.snmp_modules || ['if_mib'],
      device_type: device.device_type || 'switch', description: device.description || '',
      enabled: device.enabled, username: device.username || '',
      auth_protocol: device.auth_protocol || 'SHA', auth_password: '',
      priv_protocol: device.priv_protocol || 'AES', priv_password: '',
      assigned_agent_id: device.assigned_agent_id || '',
    });
    setShowModal(true);
  };

  const handleDelete = async (device) => {
    if (!window.confirm(`Delete "${device.name}"?`)) return;
    try {
      await deleteDevice(device.id);
      showToast(`Device "${device.name}" deleted`, 'success');
      loadData();
    } catch {
      showToast('Failed to delete device', 'error');
    }
  };

  const handleModuleChange = (e) => {
    setFormData({ ...formData, snmp_modules: Array.from(e.target.selectedOptions, o => o.value) });
  };

  const resetForm = () => {
    setEditingDevice(null);
    setFormData({
      name: '', ip_address: '', snmp_version: '2c', snmp_community: 'public',
      snmp_port: 161, snmp_modules: ['if_mib'], device_type: 'switch',
      description: '', enabled: true,
      username: '', auth_protocol: 'SHA', auth_password: '',
      priv_protocol: 'AES', priv_password: '', assigned_agent_id: '',
    });
  };

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Devices</div>
          <div className="page-subtitle">Manage network devices for SNMP collection</div>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>
          + Add Device
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>IP Address</th>
              <th>Type</th>
              <th>SNMP Version</th>
              <th>Agent</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {devices.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No devices found. Click "+ Add Device" to get started.
                </td>
              </tr>
            ) : (
              devices.map(device => (
                <tr key={device.id}>
                  <td><strong>{device.name}</strong></td>
                  <td className="font-mono text-sm">{device.ip_address}</td>
                  <td className="text-muted">{device.device_type || '—'}</td>
                  <td className="font-mono text-sm">{device.snmp_version}</td>
                  <td>
                    {device.assigned_agent_id
                      ? <code className="font-mono text-xs text-muted">{device.assigned_agent_id.slice(0, 12)}…</code>
                      : <span className="text-faint">—</span>}
                  </td>
                  <td>
                    <span className={`badge ${device.enabled ? 'badge-success' : 'badge-danger'}`}>
                      {device.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(device)}>Edit</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(device)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingDevice ? 'Edit Device' : 'Add Device'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Device Name *</label>
                <input className="input" type="text" value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  required placeholder="e.g., Router-01" />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">IP Address *</label>
                  <input className="input" type="text" value={formData.ip_address}
                    onChange={e => setFormData({ ...formData, ip_address: e.target.value })}
                    required placeholder="192.168.1.1" />
                </div>
                <div className="form-group">
                  <label className="form-label">SNMP Port</label>
                  <input className="input" type="number" value={formData.snmp_port}
                    onChange={e => setFormData({ ...formData, snmp_port: parseInt(e.target.value) })}
                    placeholder="161" />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">SNMP Version</label>
                  <select className="select" value={formData.snmp_version}
                    onChange={e => setFormData({ ...formData, snmp_version: e.target.value })}>
                    <option value="2c">v2c</option>
                    <option value="3">v3</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">SNMP Modules</label>
                  <select className="select" multiple size="3" value={formData.snmp_modules}
                    onChange={handleModuleChange} style={{ height: 'auto' }}>
                    {availableModules.map(mod => (
                      <option key={mod} value={mod}>{mod}</option>
                    ))}
                  </select>
                </div>
              </div>
              {formData.snmp_version === '2c' && (
                <div className="form-group">
                  <label className="form-label">SNMP Community</label>
                  <input className="input" type="text" value={formData.snmp_community}
                    onChange={e => setFormData({ ...formData, snmp_community: e.target.value })}
                    placeholder="public" />
                </div>
              )}
              {formData.snmp_version === '3' && (
                <>
                  <div className="form-group">
                    <label className="form-label">Username *</label>
                    <input className="input" type="text" value={formData.username}
                      onChange={e => setFormData({ ...formData, username: e.target.value })}
                      required placeholder="snmpv3user" />
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Auth Protocol</label>
                      <select className="select" value={formData.auth_protocol}
                        onChange={e => setFormData({ ...formData, auth_protocol: e.target.value })}>
                        <option value="SHA">SHA</option>
                        <option value="SHA256">SHA-256</option>
                        <option value="MD5">MD5</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Auth Password *</label>
                      <input className="input" type="password" value={formData.auth_password}
                        onChange={e => setFormData({ ...formData, auth_password: e.target.value })}
                        required placeholder="min 8 chars" />
                    </div>
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Priv Protocol</label>
                      <select className="select" value={formData.priv_protocol}
                        onChange={e => setFormData({ ...formData, priv_protocol: e.target.value })}>
                        <option value="AES">AES</option>
                        <option value="AES256">AES-256</option>
                        <option value="DES">DES</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Priv Password *</label>
                      <input className="input" type="password" value={formData.priv_password}
                        onChange={e => setFormData({ ...formData, priv_password: e.target.value })}
                        required placeholder="min 8 chars" />
                    </div>
                  </div>
                </>
              )}
              <div className="form-group">
                <label className="form-label">Assigned Agent</label>
                <select className="select" value={formData.assigned_agent_id}
                  onChange={e => setFormData({ ...formData, assigned_agent_id: e.target.value })}>
                  <option value="">— Unassigned —</option>
                  {agents.map(agent => (
                    <option key={agent.agent_id} value={agent.agent_id}>
                      {agent.hostname} ({agent.agent_id})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Device Type</label>
                <select className="select" value={formData.device_type}
                  onChange={e => setFormData({ ...formData, device_type: e.target.value })}>
                  <option value="router">Router</option>
                  <option value="switch">Switch</option>
                  <option value="firewall">Firewall</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input className="input" type="text" value={formData.description}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Optional" />
              </div>
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={formData.enabled}
                    onChange={e => setFormData({ ...formData, enabled: e.target.checked })} />
                  <span className="form-label" style={{ margin: 0 }}>Enabled</span>
                </label>
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">{editingDevice ? 'Update' : 'Create'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update AgentsPage.js — fix alert-danger, remove inline styles, add toast**

```jsx
import React, { useState, useEffect } from 'react';
import { getAgents } from '../services/api';

const STATUS_BADGE = {
  online:   'badge-success',
  degraded: 'badge-warning',
  offline:  'badge-danger',
};

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadAgents();
    const iv = setInterval(loadAgents, 30000);
    return () => clearInterval(iv);
  }, []);

  const loadAgents = async () => {
    try {
      const data = await getAgents();
      setAgents(data);
      setError(null);
    } catch {
      setError('Unable to reach manager. Is it running?');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Agents</div>
          <div className="page-subtitle">Distributed SNMP collection agents</div>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Agent ID</th>
              <th>Hostname</th>
              <th>IP</th>
              <th>Status</th>
              <th>Last Seen</th>
              <th>Pending Uploads</th>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No agents registered.
                </td>
              </tr>
            ) : (
              agents.map(agent => (
                <tr key={agent.agent_id}>
                  <td><code className="font-mono text-xs">{agent.agent_id}</code></td>
                  <td>{agent.hostname}</td>
                  <td className="font-mono text-sm">{agent.ip}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[agent.status] || 'badge-info'}`}>
                      {agent.status}
                    </span>
                  </td>
                  <td className="text-sm text-muted">
                    {agent.last_seen ? new Date(agent.last_seen).toLocaleString() : '—'}
                  </td>
                  <td className="font-mono text-sm">{agent.pending_uploads}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update ConfigurationManager.js — code-editor class, btn-warning, remove inline styles, toasts**

Replace the full file:

```jsx
import React, { useState, useEffect } from 'react';
import {
  getDevices, getSchedules, updateSchedule, createSchedule,
  reloadConfig, getModules, getModuleConfig, updateModuleConfig
} from '../services/api';
import { useToast } from '../hooks/useToast';

export default function ConfigurationManager() {
  const { showToast } = useToast();
  const [modules, setModules] = useState([]);
  const [devices, setDevices] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newSchedule, setNewSchedule] = useState({ device_id: '', interval_seconds: 60, enabled: true });
  const [selectedModule, setSelectedModule] = useState('');
  const [yamlContent, setYamlContent] = useState('');
  const [originalYaml, setOriginalYaml] = useState('');
  const [editorStatus, setEditorStatus] = useState('');

  useEffect(() => { loadInitialData(); }, []);

  useEffect(() => {
    if (selectedModule) loadModuleConfig(selectedModule);
    else { setYamlContent(''); setOriginalYaml(''); }
  }, [selectedModule]);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [modulesData, devicesData, schedulesData] = await Promise.all([
        getModules(), getDevices(), getSchedules()
      ]);
      setModules(modulesData);
      setDevices(devicesData);
      setSchedules(schedulesData);
      if (modulesData.length > 0) setSelectedModule(modulesData[0]);
    } catch {
      showToast('Failed to load configuration', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadModuleConfig = async (moduleName) => {
    setEditorStatus('loading');
    try {
      const data = await getModuleConfig(moduleName);
      setYamlContent(data.yaml);
      setOriginalYaml(data.yaml);
      setEditorStatus('');
    } catch {
      setEditorStatus('error');
      showToast('Failed to load module configuration', 'error');
    }
  };

  const handleSaveModule = async () => {
    setEditorStatus('saving');
    try {
      await updateModuleConfig(selectedModule, yamlContent);
      setOriginalYaml(yamlContent);
      setEditorStatus('');
      showToast(`Module "${selectedModule}" saved`, 'success');
    } catch (err) {
      setEditorStatus('error');
      showToast('Save failed: ' + (err.response?.data?.detail || err.message), 'error');
    }
  };

  const handleToggleSchedule = async (deviceId, sched) => {
    try {
      const updated = await updateSchedule(deviceId, { enabled: !sched.enabled });
      setSchedules(prev => prev.map(s => s.device_id === deviceId ? updated : s));
      showToast(`Schedule ${updated.enabled ? 'resumed' : 'paused'}`, 'success');
    } catch {
      showToast('Failed to update schedule', 'error');
    }
  };

  const handleIntervalChange = async (deviceId, interval) => {
    try {
      const updated = await updateSchedule(deviceId, { interval_seconds: parseInt(interval) });
      setSchedules(prev => prev.map(s => s.device_id === deviceId ? updated : s));
    } catch {
      showToast('Failed to update interval', 'error');
    }
  };

  const handleCreateSchedule = async (e) => {
    e.preventDefault();
    try {
      const created = await createSchedule(newSchedule);
      setSchedules(prev => [...prev, created]);
      setShowModal(false);
      setNewSchedule({ device_id: '', interval_seconds: 60, enabled: true });
      showToast('Schedule created', 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to create schedule'), 'error');
    }
  };

  const handleReloadConfig = async () => {
    try {
      await reloadConfig();
      showToast('Exporter reloaded successfully', 'success');
    } catch {
      showToast('Reload failed', 'error');
    }
  };

  const getDeviceSchedule = (deviceId) => schedules.find(s => s.device_id === deviceId);
  const availableDevices = devices.filter(d => !getDeviceSchedule(d.id));

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Configuration</div>
          <div className="page-subtitle">Collection schedules and SNMP module definitions</div>
        </div>
      </div>

      {/* Schedules */}
      <div className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>Device Collection Schedules</div>
            <div className="page-subtitle">Manage polling intervals and pause/resume collection.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)} disabled={availableDevices.length === 0}>
            + Add Schedule
          </button>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Device Name</th>
              <th>IP Address</th>
              <th>Interval</th>
              <th>Status</th>
              <th>Last Collection</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {devices.map(device => {
              const sched = getDeviceSchedule(device.id);
              return (
                <tr key={device.id}>
                  <td style={{ fontWeight: 500 }}>{device.name}</td>
                  <td className="font-mono text-sm text-muted">{device.ip_address}</td>
                  <td>
                    {sched ? (
                      <select className="select" style={{ padding: '0.2rem 0.5rem', width: 'auto', fontSize: 12 }}
                        value={sched.interval_seconds}
                        onChange={e => handleIntervalChange(device.id, e.target.value)}>
                        <option value="30">30s</option>
                        <option value="60">1m</option>
                        <option value="300">5m</option>
                        <option value="900">15m</option>
                        <option value="3600">1h</option>
                      </select>
                    ) : <span className="text-faint text-sm">Not scheduled</span>}
                  </td>
                  <td>
                    {sched ? (
                      <span className={`badge ${sched.enabled ? 'badge-success' : 'badge-danger'}`}>
                        {sched.enabled ? 'Active' : 'Paused'}
                      </span>
                    ) : <span className="badge" style={{ color: 'var(--color-text-faint)', borderColor: 'var(--color-border)' }}>None</span>}
                  </td>
                  <td className="text-sm text-muted">
                    {sched?.last_collection ? new Date(sched.last_collection).toLocaleString() : 'Never'}
                  </td>
                  <td>
                    {sched ? (
                      <button className={`btn btn-sm ${sched.enabled ? 'btn-secondary' : 'btn-primary'}`}
                        onClick={() => handleToggleSchedule(device.id, sched)}>
                        {sched.enabled ? 'Pause' : 'Resume'}
                      </button>
                    ) : (
                      <button className="btn btn-primary btn-sm"
                        onClick={() => { setNewSchedule({ ...newSchedule, device_id: device.id }); setShowModal(true); }}>
                        Add
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add Schedule Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Configure Collection Schedule</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleCreateSchedule}>
              <div className="form-group">
                <label className="form-label">Device</label>
                <select className="select" required value={newSchedule.device_id}
                  onChange={e => setNewSchedule({ ...newSchedule, device_id: e.target.value })}>
                  <option value="">Select a device...</option>
                  {availableDevices.map(d => (
                    <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>
                  ))}
                  {newSchedule.device_id && !availableDevices.find(d => d.id === parseInt(newSchedule.device_id)) && (
                    <option value={newSchedule.device_id}>
                      {devices.find(d => d.id === parseInt(newSchedule.device_id))?.name}
                    </option>
                  )}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Polling Interval</label>
                <select className="select" value={newSchedule.interval_seconds}
                  onChange={e => setNewSchedule({ ...newSchedule, interval_seconds: parseInt(e.target.value) })}>
                  <option value="30">30 Seconds</option>
                  <option value="60">1 Minute</option>
                  <option value="300">5 Minutes</option>
                  <option value="900">15 Minutes</option>
                  <option value="3600">1 Hour</option>
                </select>
              </div>
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={newSchedule.enabled}
                    onChange={e => setNewSchedule({ ...newSchedule, enabled: e.target.checked })} />
                  <span className="form-label" style={{ margin: 0 }}>Enable collection immediately</span>
                </label>
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={!newSchedule.device_id}>Create Schedule</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Module Editor */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>Module Definitions</div>
            <div className="page-subtitle">Edit YAML configuration for SNMP modules.</div>
          </div>
          <select className="select" style={{ width: 200 }} value={selectedModule}
            onChange={e => setSelectedModule(e.target.value)}>
            {modules.map(mod => <option key={mod} value={mod}>{mod}</option>)}
          </select>
        </div>
        <textarea
          className="code-editor"
          value={yamlContent}
          onChange={e => setYamlContent(e.target.value)}
          spellCheck="false"
          disabled={editorStatus === 'loading' || editorStatus === 'saving'}
        />
        <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-secondary"
            onClick={() => setYamlContent(originalYaml)}
            disabled={yamlContent === originalYaml || editorStatus === 'saving'}>
            Reset
          </button>
          <button className="btn btn-primary"
            onClick={handleSaveModule}
            disabled={yamlContent === originalYaml || editorStatus === 'saving'}>
            {editorStatus === 'saving' ? 'Saving...' : 'Apply Changes'}
          </button>
        </div>
      </div>

      {/* System Maintenance */}
      <div className="card" style={{ background: 'rgba(251,146,60,0.04)', borderColor: 'var(--color-warning-border)' }}>
        <div className="page-title" style={{ fontSize: 13, color: 'var(--color-warning)', marginBottom: 4 }}>
          System Maintenance
        </div>
        <div className="page-subtitle" style={{ marginBottom: 14 }}>
          Use these tools only when manual intervention is required.
        </div>
        <button className="btn btn-warning" onClick={handleReloadConfig}>
          Reload SNMP Exporter Service
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify toasts fire**

Test in the browser:
- Create a device → amber toast "Device X created" slides in top-right, auto-dismisses in 4s
- Delete a device → amber toast "Device X deleted"
- Save a module config → amber toast "Module if_mib saved"
- Pause a schedule → amber toast "Schedule paused"

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DeviceManagement.js frontend/src/components/AgentsPage.js frontend/src/components/ConfigurationManager.js
git commit -m "feat(frontend): wire toast notifications into device, agent, and config operations"
```

---

## Task 7: Table Search + Sort on Devices and Agents

**Files:**
- Modify: `src/components/DeviceManagement.js`
- Modify: `src/components/AgentsPage.js`

- [ ] **Step 1: Add search + sort state to DeviceManagement.js**

Add these three state declarations and helper at the top of the component (after existing state):

```jsx
const [search, setSearch] = useState('');
const [sort, setSort] = useState({ col: 'name', dir: 'asc' });
```

Add this computed value before the `return`:

```jsx
const filtered = devices
  .filter(d =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.ip_address.includes(search)
  )
  .sort((a, b) => {
    const valA = (a[sort.col] || '').toString().toLowerCase();
    const valB = (b[sort.col] || '').toString().toLowerCase();
    return sort.dir === 'asc'
      ? valA.localeCompare(valB)
      : valB.localeCompare(valA);
  });

function toggleSort(col) {
  setSort(prev => ({ col, dir: prev.col === col && prev.dir === 'asc' ? 'desc' : 'asc' }));
}

function sortIndicator(col) {
  if (sort.col !== col) return '';
  return sort.dir === 'asc' ? ' ↑' : ' ↓';
}
```

Replace the `page-header` block to add the search input:

```jsx
<div className="page-header">
  <div>
    <div className="page-title">Devices</div>
    <div className="page-subtitle">Manage network devices for SNMP collection</div>
  </div>
  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
    <input
      className="input table-search"
      type="search"
      placeholder="Search by name or IP…"
      value={search}
      onChange={e => setSearch(e.target.value)}
    />
    <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>
      + Add Device
    </button>
  </div>
</div>
```

Replace the `<thead>` with sortable headers:

```jsx
<thead>
  <tr>
    <th className="sortable" onClick={() => toggleSort('name')}>Name{sortIndicator('name')}</th>
    <th className="sortable" onClick={() => toggleSort('ip_address')}>IP Address{sortIndicator('ip_address')}</th>
    <th>Type</th>
    <th>SNMP Version</th>
    <th>Agent</th>
    <th className="sortable" onClick={() => toggleSort('enabled')}>Status{sortIndicator('enabled')}</th>
    <th>Actions</th>
  </tr>
</thead>
```

Replace `devices.map(device => (...))` with `filtered.map(device => (...))` in the tbody — the row JSX inside the map is unchanged from Task 6 Step 1.

Also update the empty-state `<tr>` (the one that currently shows "No devices found") to differentiate between no devices and no search results:

```jsx
{filtered.length === 0 ? (
  <tr>
    <td colSpan="7" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
      {search ? `No devices match "${search}"` : 'No devices found. Click "+ Add Device" to get started.'}
    </td>
  </tr>
) : (
  filtered.map(device => (
    <tr key={device.id}>
      <td><strong>{device.name}</strong></td>
      <td className="font-mono text-sm">{device.ip_address}</td>
      <td className="text-muted">{device.device_type || '—'}</td>
      <td className="font-mono text-sm">{device.snmp_version}</td>
      <td>
        {device.assigned_agent_id
          ? <code className="font-mono text-xs text-muted">{device.assigned_agent_id.slice(0, 12)}…</code>
          : <span className="text-faint">—</span>}
      </td>
      <td>
        <span className={`badge ${device.enabled ? 'badge-success' : 'badge-danger'}`}>
          {device.enabled ? 'Enabled' : 'Disabled'}
        </span>
      </td>
      <td>
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(device)}>Edit</button>
          <button className="btn btn-danger btn-sm" onClick={() => handleDelete(device)}>Delete</button>
        </div>
      </td>
    </tr>
  ))
)}
```

- [ ] **Step 2: Add search + sort to AgentsPage.js**

Add state after existing state declarations:

```jsx
const [search, setSearch] = useState('');
const [sort, setSort] = useState({ col: 'hostname', dir: 'asc' });
```

Add before the `return`:

```jsx
const filtered = agents
  .filter(a =>
    (a.hostname || '').toLowerCase().includes(search.toLowerCase()) ||
    (a.ip || '').includes(search)
  )
  .sort((a, b) => {
    const valA = (a[sort.col] || '').toString().toLowerCase();
    const valB = (b[sort.col] || '').toString().toLowerCase();
    return sort.dir === 'asc'
      ? valA.localeCompare(valB)
      : valB.localeCompare(valA);
  });

function toggleSort(col) {
  setSort(prev => ({ col, dir: prev.col === col && prev.dir === 'asc' ? 'desc' : 'asc' }));
}
function sortIndicator(col) {
  if (sort.col !== col) return '';
  return sort.dir === 'asc' ? ' ↑' : ' ↓';
}
```

Update the `page-header` to include the search input:

```jsx
<div className="page-header">
  <div>
    <div className="page-title">Agents</div>
    <div className="page-subtitle">Distributed SNMP collection agents</div>
  </div>
  <input
    className="input table-search"
    type="search"
    placeholder="Search by hostname or IP…"
    value={search}
    onChange={e => setSearch(e.target.value)}
  />
</div>
```

Update `<thead>` with sortable headers:

```jsx
<thead>
  <tr>
    <th>Agent ID</th>
    <th className="sortable" onClick={() => toggleSort('hostname')}>Hostname{sortIndicator('hostname')}</th>
    <th className="sortable" onClick={() => toggleSort('ip')}>IP{sortIndicator('ip')}</th>
    <th className="sortable" onClick={() => toggleSort('status')}>Status{sortIndicator('status')}</th>
    <th>Last Seen</th>
    <th>Pending Uploads</th>
  </tr>
</thead>
```

Replace `agents.map(...)` in tbody with `filtered.map(...)`.

- [ ] **Step 3: Verify search and sort**

On the Devices page:
- Type a partial device name in the search box — table filters in real time
- Type an IP like "192.168" — filters by IP
- Click "Name" column header — sorts ascending (↑), click again — descending (↓)
- Clear search — all devices return

On the Agents page: same behavior for hostname/IP/status columns.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/DeviceManagement.js frontend/src/components/AgentsPage.js
git commit -m "feat(frontend): add search filter and sortable columns to devices and agents tables"
```

---

## Task 8: MetricsViewer — Replace glass-card with card

**Files:**
- Modify: `src/components/MetricsViewer.js`

- [ ] **Step 1: Replace all glass-card class references in MetricsViewer.js**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector/frontend/src/components
grep -n "glass-card" MetricsViewer.js
```

For each line found, change `className="glass-card"` to `className="card"`. Also change any `className="container"` wrapping divs to remove the container class (pages now use `page-content` padding from App.css).

Also update the page header in MetricsViewer.js to use the new classes:

Find the existing page header block and replace with:
```jsx
<div className="page-header">
  <div className="page-title">Metrics Explorer</div>
</div>
```

- [ ] **Step 2: Verify MetricsViewer renders correctly**

Navigate to /metrics. Expect:
- Selection dropdowns in a card (same background as other pages, no glass blur)
- Charts render in cards (same styling)
- No visual regressions in chart colors or tooltips

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MetricsViewer.js
git commit -m "feat(frontend): update MetricsViewer to use card class and new page-header pattern"
```

---

## Final Verification

- [ ] Log in at http://localhost:3000/login — two-panel layout, amber brand panel, styled form
- [ ] After login — sidebar visible, Dashboard loads with stat cards and charts
- [ ] Navigate all 5 pages — active nav item highlighted amber with left border
- [ ] Devices page — search filters in real time, columns sort on click
- [ ] Add a device — amber success toast appears top-right, auto-dismisses
- [ ] Agents page — alert renders styled (not invisible) if manager is down
- [ ] Config page — YAML editor uses monospace font, btn-warning is styled amber
- [ ] Metrics page — no visual regressions in chart rendering
- [ ] Browser console — no React warnings or uncaught errors

```bash
git log --oneline -10
```

Expected commits (in order):
```
feat(frontend): update MetricsViewer to use card class and new page-header pattern
feat(frontend): add search filter and sortable columns to devices and agents tables
feat(frontend): wire toast notifications into device, agent, and config operations
feat(frontend): add toast notification system
feat(frontend): redesign dashboard with charts, agent status, events feed
feat(frontend): redesign login page with two-panel layout
feat(frontend): add left sidebar nav, app-shell layout, replace top navbar
feat(frontend): replace design system with Graphite Amber tokens and CSS
```
