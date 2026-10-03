// Single source for the app's navigation: the sidebar renders it and the
// command palette searches it.
export const NAV_SECTIONS = [
  {
    label: 'Monitor',
    items: [
      { to: '/', icon: 'dashboard', label: 'Dashboard', keywords: 'home overview alerts' },
      { to: '/devices', icon: 'devices', label: 'Devices', keywords: 'inventory hosts switches' },
      {
        to: '/metrics',
        icon: 'metrics',
        label: 'Metrics',
        keywords: 'interfaces bandwidth charts',
      },
      { to: '/topology', icon: 'topology', label: 'Topology', keywords: 'map lldp network' },
      { to: '/traps', icon: 'traps', label: 'Traps', keywords: 'snmp events notifications' },
    ],
  },
  {
    label: 'Collection',
    items: [
      { to: '/agents', icon: 'agents', label: 'Agents', keywords: 'collectors pollers' },
      { to: '/config', icon: 'config', label: 'Configuration', keywords: 'oid whitelist settings' },
      { to: '/mib-browser', icon: 'mib', label: 'MIB Browser', keywords: 'walk oid' },
    ],
  },
  {
    label: 'Alerting',
    items: [
      {
        to: '/notifications',
        icon: 'notifications',
        label: 'Notifications',
        keywords: 'email webhook channels',
      },
      {
        to: '/maintenance',
        icon: 'maintenance',
        label: 'Maintenance',
        keywords: 'windows suppress',
      },
    ],
  },
  {
    label: 'Admin',
    adminOnly: true,
    items: [
      { to: '/users', icon: 'users', label: 'Users', keywords: 'accounts roles' },
      { to: '/audit', icon: 'audit', label: 'Audit Log', keywords: 'history changes compliance' },
    ],
  },
];

export function visibleSections(role) {
  return NAV_SECTIONS.filter((s) => !s.adminOnly || role === 'admin');
}
