# UI

React app built with Create React App (`react-scripts`), served as a static bundle by the frontend container behind nginx. API calls go to `/api/*`.

## Structure (`frontend/src/`)

| Path | Contents |
|---|---|
| `App.js` | routes, layout shell, auth gating via `components/PrivateRoute.js` |
| `navConfig.js` | **single source of navigation**: `NAV_SECTIONS` (Monitor, Collection, Alerting, …) with `to`, `icon`, `label`, `keywords`. The sidebar renders it and the command palette searches it |
| `pages/` | `LoginPage`, `ChangePasswordPage`, `UserManagementPage`, `AuditPage` |
| `components/` | feature screens and widgets: `Dashboard`, `DeviceManagement`, `DeviceMetrics`, `InterfacePanel`/`InterfaceCard`/`InterfaceChart`, `TopologyMap`, `TrapsPage`, `AgentsPage`, `ConfigurationManager`, `MibBrowser`, `MaintenanceWindows`, `NotificationSettings`, `Sidebar`, `CommandPalette`, `HealthBar`, `SessionMonitor`, `ToastContainer`, `Icon` |
| `hooks/` | `useAuth`, `useSignOut`, `useTheme`, `useToast`, `usePolledResource` |
| `services/api.js` | the API client (token handling, pagination helpers such as `getDevices()` paging through `X-Total-Count`) |
| `utils/` | `commandSearch.js` (palette matching), `format.js`, `cssVar.js` |
| `index.css`, `App.css` | design tokens and global styles |

## Patterns to follow

- **Data fetching**: use `usePolledResource` for anything that refreshes (one request per key, pauses on hidden tabs, backs off on errors). Current cadence: `/fleet/summary` and `/alerts` every 30 s, `/fleet/traffic` every 60 s. Do not add raw `setInterval` fetches.
- **Lists** are paginated server-side; read `X-Total-Count`.
- **Navigation**: add pages to `navConfig.js` (with good `keywords`) so they appear in both the sidebar and the command palette.
- **Theming**: `useTheme` stores `light`/`dark`/`system` under the `snmp-theme` localStorage key and sets `data-theme` on `<html>` (`system` follows `prefers-color-scheme`). Use CSS custom properties from `index.css` (read them in JS with `utils/cssVar.js`, e.g. for chart colors) instead of hard-coded colors.
- **Icons**: use `components/Icon.js`.
- **Feedback**: toasts via `useToast`; session expiry is handled by `SessionMonitor`.
- **Roles**: hide or disable admin/editor actions for lower roles, but rely on the backend for enforcement.
- Formatting: Prettier and ESLint (`--max-warnings=0`) run in CI on `frontend/src`.

## Developing

- `npm start` in `frontend/` gives hot reload outside Docker. Inside Docker, rebuild: `docker-compose build frontend && docker-compose up -d frontend`.
- Tests live next to components (`*.test.js`) and run with `npm test` / `npm run test:ci`.
- The end-to-end smoke test is `e2e/smoke.spec.js` (Playwright).
- Per-device alert thresholds are edited in the Device edit modal.
