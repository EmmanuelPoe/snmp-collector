import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const MONITOR_ITEMS = [
  { to: '/',        icon: '◈', label: 'Dashboard' },
  { to: '/devices', icon: '◻', label: 'Devices' },
  { to: '/metrics', icon: '▦', label: 'Metrics' },
  { to: '/agents',  icon: '◎', label: 'Agents' },
];

const MANAGE_ITEMS = [
  { to: '/config', icon: '⊞', label: 'Configuration' },
];

const ADMIN_ITEMS = [
  { to: '/users', icon: '◉', label: 'Users' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const sections = [
    { label: 'Monitor', items: MONITOR_ITEMS },
    { label: 'Manage', items: user?.role === 'admin' ? [...MANAGE_ITEMS, ...ADMIN_ITEMS] : MANAGE_ITEMS },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">⬡ SNMP Monitor</div>
        <div className="sidebar-brand-sub">infrastructure</div>
      </div>

      <nav className="sidebar-nav">
        {sections.map(section => (
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
        <NavLink to="/change-password" className="sidebar-logout">
          Change Password
        </NavLink>
        <button className="sidebar-logout" onClick={handleLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
