import React, { useState, useEffect, useCallback } from 'react';
import { getDevices, getAgents, getMetrics, getInterfaceRates, getAlerts, getDeviceTags } from '../services/api';
import { useToast } from '../hooks/useToast';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts';

const DEVICE_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'];
const TIME_RANGES = [{ label: '1h', hours: 1 }, { label: '6h', hours: 6 }, { label: '24h', hours: 24 }];

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
  const { showToast } = useToast();
  const [devices, setDevices] = useState([]);
  const [agents, setAgents] = useState([]);
  const [trafficData, setTrafficData] = useState([]);
  const [events, setEvents] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [trafficHours, setTrafficHours] = useState(1);
  const [deviceNames, setDeviceNames] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [tagFilter, setTagFilter] = useState('');
  const [secsAgo, setSecsAgo] = useState(0);
  const prevAlertIds = React.useRef(new Set());

  const loadData = useCallback(async () => {
    try {
      const [devicesRes, agentsRes, tagsRes] = await Promise.all([
        getDevices(),
        getAgents().catch(() => []),
        getDeviceTags().catch(() => []),
      ]);
      setAllTags(tagsRes);
      setDevices(devicesRes);
      setAgents(agentsRes);
      const ratesResults = await Promise.all(
        devicesRes.map(d => getInterfaceRates(d.id, trafficHours).catch(() => null))
      );
      const ratesMap = {};
      devicesRes.forEach((d, i) => { if (ratesResults[i]) ratesMap[d.name] = ratesResults[i]; });
      setDeviceNames(devicesRes.map(d => d.name));
      setTrafficData(buildPerDeviceSeries(ratesMap));
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  }, [trafficHours]);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 30000);
    return () => clearInterval(iv);
  }, [loadData]);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await getAlerts();
        setAlerts(data);
        const newIds = new Set(data.map(a => a.id));
        data.forEach(a => {
          if (!prevAlertIds.current.has(a.id)) showToast(a.message, 'error');
        });
        prevAlertIds.current = newIds;
      } catch {
        // non-fatal
      }
    };
    poll();
    const iv = setInterval(poll, 30000);
    return () => clearInterval(iv);
  }, [showToast]);

  useEffect(() => {
    if (!lastUpdated) return;
    setSecsAgo(0);
    const iv = setInterval(() => setSecsAgo(s => s + 1), 1000);
    return () => clearInterval(iv);
  }, [lastUpdated]);

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

  const visibleDeviceNames = tagFilter
    ? devices.filter(d => d.tags?.includes(tagFilter)).map(d => d.name)
    : deviceNames;

  const totalDevices = devices.length;
  const activeDevices = devices.filter(d => d.enabled).length;
  const onlineAgents = agents.filter(a => a.status === 'online').length;

  const deviceStatusData = [
    { label: 'Active', count: activeDevices },
    { label: 'Disabled', count: totalDevices - activeDevices },
  ];

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Dashboard</div>
          {lastUpdated && (
            <div className="page-subtitle">
              {secsAgo < 5 ? 'updated just now' : `updated ${secsAgo}s ago`}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {allTags.length > 0 && (
            <select
              className="input"
              value={tagFilter}
              onChange={e => setTagFilter(e.target.value)}
              style={{ width: 'auto' }}
            >
              <option value="">All devices</option>
              {allTags.map(tag => (
                <option key={tag} value={tag}>{tag}</option>
              ))}
            </select>
          )}
          <span className="live-badge"><span className="live-dot" />LIVE</span>
        </div>
      </div>

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
          <div className="stat-label">Open Alerts</div>
          <div className="stat-value" style={{ color: alerts.length > 0 ? 'var(--color-error)' : 'var(--color-success)' }}>
            {alerts.length}
          </div>
          <div className="stat-sub">
            {alerts.length === 0 ? 'all clear' : `${alerts.length} active`}
          </div>
        </div>
      </div>

      <div className="charts-row">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div className="chart-title">Network Traffic · Per Device</div>
            <div style={{ display: 'flex', gap: 4 }}>
              {TIME_RANGES.map(({ label, hours }) => (
                <button key={label} onClick={() => setTrafficHours(hours)} style={{ background: trafficHours === hours ? 'var(--color-accent)' : 'var(--color-bg)', color: trafficHours === hours ? '#fff' : 'var(--color-text-muted)', border: `1px solid ${trafficHours === hours ? 'var(--color-accent)' : 'var(--color-border)'}`, padding: '2px 8px', borderRadius: 4, fontSize: 11, cursor: 'pointer' }}>{label}</button>
              ))}
            </div>
          </div>
          {trafficData.length > 0 && visibleDeviceNames.length > 0 ? (
            <ResponsiveContainer width="100%" height={90}>
              <LineChart data={trafficData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: 'var(--color-text-faint)', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
                <YAxis hide />
                <Tooltip contentStyle={{ backgroundColor: '#fff', border: '1px solid var(--color-border)', borderRadius: 4, fontSize: 11 }} formatter={v => formatBytes(v)} />
                {visibleDeviceNames.map((name, i) => (
                  <Line key={name} type="monotone" dataKey={name} stroke={DEVICE_COLORS[i % DEVICE_COLORS.length]} strokeWidth={1.5} dot={false} connectNulls />
                ))}
              </LineChart>
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

      <div className="detail-row">
        <div className="card">
          <div className="chart-title">Active Alerts</div>
          {alerts.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 8 }}>
              <span style={{ color: 'var(--color-success)', fontSize: 14 }}>✓</span>
              <span className="text-faint text-xs">All clear</span>
            </div>
          ) : (
            alerts.map(alert => {
              const sevColor = { critical: 'var(--color-error)', warning: 'var(--color-warning, #d97706)', info: 'var(--color-text-faint)' }[alert.severity] || 'var(--color-error)';
              return (
              <div key={alert.id} className="agent-row">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {alert.severity && (
                      <span className="badge" style={{ background: sevColor, color: '#fff', fontSize: 10, textTransform: 'uppercase', padding: '1px 6px' }}>
                        {alert.severity}
                      </span>
                    )}
                    <span className="agent-name" style={{ color: sevColor, fontSize: 12 }}>
                      {alert.alert_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="agent-meta">{alert.message}</div>
                </div>
                <span className="text-faint text-xs">
                  {Math.round((Date.now() - new Date(alert.triggered_at)) / 60000)}m ago
                </span>
              </div>
            );})
          )}
        </div>

        <div className="card">
          <div className="chart-title">Agent Status</div>
          {agents.length === 0 ? (
            <p className="text-faint text-xs" style={{ paddingTop: 8 }}>No agents registered.</p>
          ) : (
            [...agents].sort((a, b) => {
              const order = { online: 0, degraded: 1, offline: 2 };
              return (order[a.status] ?? 3) - (order[b.status] ?? 3);
            }).map(agent => (
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

function buildPerDeviceSeries(ratesMap) {
  const buckets = {};
  for (const [deviceName, ratesData] of Object.entries(ratesMap)) {
    if (!ratesData?.interfaces) continue;
    for (const ifaceData of Object.values(ratesData.interfaces)) {
      for (const pt of (ifaceData.sparkline || [])) {
        const d = new Date(pt.timestamp);
        const bucket = `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
        if (!buckets[bucket]) buckets[bucket] = { time: bucket };
        buckets[bucket][deviceName] = (buckets[bucket][deviceName] || 0) + pt.in_bps + pt.out_bps;
      }
    }
  }
  return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time));
}
