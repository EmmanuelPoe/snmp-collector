import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getFleetSummary, getTraps, logoutServer } from '../services/api';
import { usePolledResource } from '../hooks/usePolledResource';
import { useTheme } from '../hooks/useTheme';
import Icon from './Icon';

function readCollapsed() {
  try {
    return localStorage.getItem('sidebar-collapsed') === 'true';
  } catch {
    return false;
  }
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { theme, cycle: cycleTheme } = useTheme();
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

  function handleLogout() {
    logoutServer(); // revoke server-side (best effort, fire-and-forget)
    logout();
    navigate('/login');
  }

  const sections = [
    {
      label: 'Monitor',
      items: [
        {
          to: '/',
          icon: 'dashboard',
          label: 'Dashboard',
          badge: alertCount > 0 ? alertCount : null,
          badgeClass: 'badge-danger',
        },
        { to: '/devices', icon: 'devices', label: 'Devices' },
        { to: '/metrics', icon: 'metrics', label: 'Metrics' },
        { to: '/topology', icon: 'topology', label: 'Topology' },
        {
          to: '/traps',
          icon: 'traps',
          label: 'Traps',
          badge: trapCount > 0 ? trapCount : null,
          badgeClass: 'badge-warning',
        },
      ],
    },
    {
      label: 'Collection',
      items: [
        { to: '/agents', icon: 'agents', label: 'Agents' },
        { to: '/config', icon: 'config', label: 'Configuration' },
        { to: '/mib-browser', icon: 'mib', label: 'MIB Browser' },
      ],
    },
    {
      label: 'Alerting',
      items: [
        { to: '/notifications', icon: 'notifications', label: 'Notifications' },
        { to: '/maintenance', icon: 'maintenance', label: 'Maintenance' },
      ],
    },
    ...(user?.role === 'admin'
      ? [
          {
            label: 'Admin',
            items: [
              { to: '/users', icon: 'users', label: 'Users' },
              { to: '/audit', icon: 'audit', label: 'Audit Log' },
            ],
          },
        ]
      : []),
  ];

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
                {!collapsed && item.badge && (
                  <span className={`nav-badge ${item.badgeClass}`}>
                    {item.badge > 99 ? '99+' : item.badge}
                  </span>
                )}
                {collapsed && item.badge && <span className="nav-badge-dot" />}
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
            onClick={handleLogout}
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
