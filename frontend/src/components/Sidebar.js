import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getFleetSummary, getTraps } from '../services/api';
import { usePolledResource } from '../hooks/usePolledResource';
import { useTheme } from '../hooks/useTheme';
import { useSignOut } from '../hooks/useSignOut';
import Icon from './Icon';
import { visibleSections } from '../navConfig';
import { useCommandPalette } from './CommandPalette';

function readCollapsed() {
  try {
    return localStorage.getItem('sidebar-collapsed') === 'true';
  } catch {
    return false;
  }
}

export default function Sidebar() {
  const { user } = useAuth();
  const { theme, cycle: cycleTheme } = useTheme();
  const palette = useCommandPalette();
  const signOut = useSignOut();
  const [collapsed, setCollapsed] = useState(readCollapsed);

  // Shared with the dashboard: one request per interval however many widgets ask.
  const { data: summary } = usePolledResource('fleet-summary', getFleetSummary);
  const { data: traps } = usePolledResource('traps-1h', () => getTraps({ hours: 1, limit: 200 }), {
    intervalMs: 60000,
  });
  const alertCount = summary?.alerts.open ?? 0;
  const trapCount = traps?.length ?? 0;

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('sidebar-collapsed', next);
      } catch {
        // storage blocked: collapse still applies for this session
      }
      return next;
    });
  }

  const badges = {
    '/': alertCount > 0 ? { value: alertCount, className: 'badge-danger' } : null,
    '/traps': trapCount > 0 ? { value: trapCount, className: 'badge-warning' } : null,
  };
  const sections = visibleSections(user?.role);

  const themeIcon = { system: 'system', light: 'sun', dark: 'moon' }[theme];
  const themeLabel = { system: 'System', light: 'Light', dark: 'Dark' }[theme];

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      <div className="sidebar-brand">
        <div className="sidebar-brand-inner">
          <div className="sidebar-brand-mark">
            <Icon name="logo" size={20} />
          </div>
          {!collapsed && (
            <div className="sidebar-brand-text">
              <div className="sidebar-brand-name">SNMP Monitor</div>
              <div className="sidebar-brand-sub">infrastructure</div>
            </div>
          )}
          <button
            className="sidebar-collapse-btn"
            onClick={toggle}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <Icon name={collapsed ? 'chevronRight' : 'chevronLeft'} size={14} />
          </button>
        </div>
      </div>

      <button
        className="sidebar-search"
        onClick={palette.open}
        aria-label="Search (command palette)"
        title={`Search (${palette.shortcutLabel})`}
      >
        <Icon name="search" size={15} />
        {!collapsed && (
          <>
            <span className="sidebar-search-text">Search…</span>
            <kbd className="kbd">{palette.shortcutLabel}</kbd>
          </>
        )}
      </button>

      <nav className="sidebar-nav">
        {sections.map((section) => (
          <div key={section.label}>
            {!collapsed && <div className="sidebar-section-label">{section.label}</div>}
            {collapsed && <div className="sidebar-section-divider" />}
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">
                  <Icon name={item.icon} size={16} />
                </span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
                {!collapsed && badges[item.to] && (
                  <span className={`nav-badge ${badges[item.to].className}`}>
                    {badges[item.to].value > 99 ? '99+' : badges[item.to].value}
                  </span>
                )}
                {collapsed && badges[item.to] && <span className="nav-badge-dot" />}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        {!collapsed && user && (
          <div className="sidebar-user">
            <div className="user-online-dot" />
            <div>
              <div className="sidebar-user-email">{user.email}</div>
              <div className="sidebar-user-role">{user.role || 'user'}</div>
            </div>
          </div>
        )}
        <div className={`sidebar-actions${collapsed ? ' collapsed' : ''}`}>
          <button
            className="sidebar-action"
            onClick={cycleTheme}
            title={`Theme: ${themeLabel} (click to change)`}
            aria-label={`Theme: ${themeLabel}. Switch theme`}
          >
            <Icon name={themeIcon} size={15} />
            {!collapsed && <span>{themeLabel}</span>}
          </button>
          <NavLink
            to="/change-password"
            className="sidebar-action"
            title="Change password"
            aria-label="Change password"
          >
            <Icon name="key" size={15} />
            {!collapsed && <span>Password</span>}
          </NavLink>
          <button
            className="sidebar-action sidebar-action-danger"
            onClick={signOut}
            title="Sign out"
            aria-label="Sign out"
          >
            <Icon name="logout" size={15} />
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}
