import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getAlertCount, getTraps } from '../services/api';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [alertCount, setAlertCount] = useState(0);
  const [trapCount, setTrapCount] = useState(0);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebar-collapsed') === 'true'
  );

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await getAlertCount();
        setAlertCount(data.open);
      } catch {
        // non-fatal
      }
    };
    poll();
    const iv = setInterval(poll, 30000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await getTraps({ hours: 1, limit: 200 });
        setTrapCount(data.length);
      } catch {
        // non-fatal
      }
    };
    poll();
    const iv = setInterval(poll, 30000);
    return () => clearInterval(iv);
  }, []);

  function toggle() {
    setCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('sidebar-collapsed', next);
      return next;
    });
  }

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const MONITOR_ITEMS = [
    { to: '/',        icon: '◈', label: 'Dashboard',     badge: alertCount > 0 ? alertCount : null, badgeClass: 'badge-danger' },
    { to: '/devices', icon: '◻', label: 'Devices' },
    { to: '/metrics', icon: '▦', label: 'Metrics' },
    { to: '/agents',  icon: '◎', label: 'Agents' },
    { to: '/traps',   icon: '⊿', label: 'Traps',         badge: trapCount > 0 ? trapCount : null, badgeClass: 'badge-warning' },
  ];

  const MANAGE_ITEMS = [
    { to: '/config', icon: '⊞', label: 'Configuration' },
    { to: '/mib-browser', icon: '◳', label: 'MIB Browser' },
    { to: '/notifications', icon: '✉', label: 'Notifications' },
    { to: '/maintenance', icon: '⚒', label: 'Maintenance' },
  ];

  const ADMIN_ITEMS = [
    { to: '/users', icon: '◉', label: 'Users' },
  ];

  const sections = [
    { label: 'Monitor', items: MONITOR_ITEMS },
    { label: 'Manage', items: user?.role === 'admin' ? [...MANAGE_ITEMS, ...ADMIN_ITEMS] : MANAGE_ITEMS },
  ];

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      <div className="sidebar-brand">
        <div className="sidebar-brand-inner">
          {!collapsed && (
            <div>
              <div className="sidebar-brand-name">⬡ SNMP Monitor</div>
              <div className="sidebar-brand-sub">infrastructure</div>
            </div>
          )}
          {collapsed && <div className="sidebar-brand-icon">⬡</div>}
          <button className="sidebar-collapse-btn" onClick={toggle} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? '›' : '‹'}
          </button>
        </div>
      </div>

      <nav className="sidebar-nav">
        {sections.map(section => (
          <div key={section.label}>
            {!collapsed && <div className="sidebar-section-label">{section.label}</div>}
            {collapsed && <div className="sidebar-section-divider" />}
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
                {!collapsed && item.badge && (
                  <span className={`nav-badge ${item.badgeClass}`}>
                    {item.badge}
                  </span>
                )}
                {collapsed && item.badge && (
                  <span className="nav-badge-dot" />
                )}
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
        {!collapsed && (
          <>
            <NavLink to="/change-password" className="sidebar-logout">
              Change Password
            </NavLink>
            <button className="sidebar-logout" onClick={handleLogout}>
              Sign out
            </button>
          </>
        )}
        {collapsed && (
          <button className="sidebar-logout sidebar-logout-icon" onClick={handleLogout} title="Sign out">
            ⏻
          </button>
        )}
      </div>
    </aside>
  );
}
