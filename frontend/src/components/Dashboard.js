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
