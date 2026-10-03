import React, { useState, useEffect } from 'react';
import {
  getAgents,
  getAlertsPage,
  getFleetSummary,
  getFleetTraffic,
  acknowledgeAlert,
  assignAlert,
  setAlertNote,
  getAssignableUsers,
} from '../services/api';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import { formatBps } from '../utils/format';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from 'recharts';

const NO_AGENTS = [];
const ALERT_PAGE_SIZE = 50;
// A burst larger than this collapses into one toast instead of one per alert.
const TOAST_BURST_LIMIT = 3;
const TIME_RANGES = [
  { label: '1h', hours: 1 },
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
];

const STATUS_BADGE = {
  online: 'badge-success',
  degraded: 'badge-warning',
  offline: 'badge-danger',
};

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
  const { user } = useAuth();
  const canManageAlerts = user?.role === 'admin' || user?.role === 'editor';
  const [assignableUsers, setAssignableUsers] = useState([]);
  const [events, setEvents] = useState([]);
  const [trafficHours, setTrafficHours] = useState(1);
  const [alerts, setAlerts] = useState([]);
  const [alertTotal, setAlertTotal] = useState(0);
  const [alertLimit, setAlertLimit] = useState(ALERT_PAGE_SIZE);
  const [severityFilter, setSeverityFilter] = useState('');
  const [topBy, setTopBy] = useState('top_by_traffic');
  const [secsAgo, setSecsAgo] = useState(0);
  // Highest alert id already shown. null until the first page lands (no toasts for the
  // backlog). Ids only grow, so paging, resolving or a bigger page size can't look "new".
  const alertWatermark = React.useRef(null);

  const {
    data: summary,
    error: summaryError,
    refresh: refreshSummary,
    updatedAt: lastUpdated,
  } = usePolledResource('fleet-summary', getFleetSummary);
  const { data: traffic } = usePolledResource(
    `fleet-traffic:${trafficHours}`,
    () => getFleetTraffic(trafficHours, 10),
    { intervalMs: 60000 },
  );
  const { data: agentsData } = usePolledResource('agents', () => getAgents().catch(() => []));
  const agents = agentsData || NO_AGENTS;

  const alertFeedKey = `alerts:${severityFilter}:${alertLimit}`;
  const { data: alertPage } = usePolledResource(alertFeedKey, () =>
    getAlertsPage({ limit: alertLimit, ...(severityFilter && { severity: severityFilter }) }),
  );

  useEffect(() => {
    if (!alertPage) return;
    setAlerts(alertPage.items);
    setAlertTotal(alertPage.total);
    const mark = alertWatermark.current;
    const maxId = Math.max(0, ...alertPage.items.map((a) => a.id));
    alertWatermark.current = Math.max(mark ?? 0, maxId);
    if (mark === null) return;
    const fresh = alertPage.items.filter((a) => a.id > mark);
    if (fresh.length > TOAST_BURST_LIMIT) {
      const critical = fresh.filter((a) => a.severity === 'critical').length;
      showToast(`${fresh.length} new alerts (${critical} critical)`, 'error');
    } else {
      fresh.forEach((a) => showToast(a.message, 'error'));
    }
  }, [alertPage, showToast]);

  // Changing the filter swaps feeds; don't announce the other feed's alerts.
  useEffect(() => {
    alertWatermark.current = null;
  }, [severityFilter]);

  useEffect(() => {
    if (!canManageAlerts) return;
    getAssignableUsers()
      .then(setAssignableUsers)
      .catch(() => {});
  }, [canManageAlerts]);

  const _applyAlertUpdate = (updated) =>
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));

  const handleAck = async (alert) => {
    try {
      _applyAlertUpdate(await acknowledgeAlert(alert.id));
    } catch {
      showToast('Failed to acknowledge alert', 'error');
    }
  };

  const handleAssign = async (alert, value) => {
    try {
      _applyAlertUpdate(await assignAlert(alert.id, value === '' ? null : Number(value)));
    } catch {
      showToast('Failed to assign alert', 'error');
    }
  };

  const handleNote = async (alert) => {
    const note = window.prompt('Note for this alert:', alert.note || '');
    if (note === null) return;
    try {
      _applyAlertUpdate(await setAlertNote(alert.id, note));
    } catch {
      showToast('Failed to save note', 'error');
    }
  };

  useEffect(() => {
    if (!lastUpdated) return;
    setSecsAgo(0);
    const iv = setInterval(() => setSecsAgo((s) => s + 1), 1000);
    return () => clearInterval(iv);
  }, [lastUpdated]);

  useEffect(() => {
    if (agents.length === 0) return;
    const degraded = agents.filter((a) => a.status !== 'online');
    if (degraded.length > 0) {
      setEvents((prev) =>
        [
          {
            time: new Date(),
            text: `${degraded[0].hostname || degraded[0].agent_id} status: ${degraded[0].status}`,
          },
          ...prev,
        ].slice(0, 8),
      );
    }
  }, [agents]);

  if (!summary && summaryError) {
    return (
      <div className="loading-center" role="alert" style={{ flexDirection: 'column', gap: 12 }}>
        <div>Couldn't load the fleet summary. Retrying automatically.</div>
        <button className="btn btn-secondary" onClick={refreshSummary}>
          Retry now
        </button>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="loading-center">
        <div className="spinner" />
      </div>
    );
  }

  const { devices: dev, alerts: alertStats } = summary;
  const onlineAgents = agents.filter((a) => a.status === 'online').length;
  const topRows = traffic?.[topBy] || [];
  const trafficSeries = (traffic?.series || []).map((p) => ({
    ...p,
    time: formatTime(p.timestamp),
  }));

  const deviceStatusData = [
    { label: 'Up', count: dev.up, color: 'var(--color-success)' },
    { label: 'Degraded', count: dev.degraded, color: 'var(--color-warning, #d97706)' },
    { label: 'Down', count: dev.down, color: 'var(--color-error)' },
    { label: 'Disabled', count: dev.disabled, color: 'var(--color-text-faint)' },
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
          <span className="live-badge">
            <span className="live-dot" />
            LIVE
          </span>
        </div>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Devices</div>
          <div className="stat-value">{dev.total.toLocaleString()}</div>
          <div className="stat-sub">
            {dev.up.toLocaleString()} up
            {dev.disabled > 0 && ` · ${dev.disabled.toLocaleString()} disabled`}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Down / Degraded</div>
          <div
            className="stat-value"
            style={{
              color:
                dev.down > 0
                  ? 'var(--color-error)'
                  : dev.degraded > 0
                    ? 'var(--color-warning, #d97706)'
                    : 'var(--color-success)',
            }}
          >
            {dev.down.toLocaleString()}
            <span style={{ fontSize: 13, color: 'var(--color-text-faint)' }}>
              {' '}
              / {dev.degraded.toLocaleString()}
            </span>
          </div>
          <div className="stat-sub">
            {dev.down === 0 && dev.degraded === 0 ? 'all devices healthy' : 'need attention'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Agents Online</div>
          <div className="stat-value white">
            {onlineAgents}{' '}
            <span style={{ fontSize: 13, color: 'var(--color-text-faint)' }}>
              / {agents.length}
            </span>
          </div>
          <div className="stat-sub">
            {onlineAgents === agents.length && agents.length > 0 ? (
              <span className="text-success">all healthy</span>
            ) : agents.length === 0 ? (
              'none registered'
            ) : (
              <span className="text-error">{agents.length - onlineAgents} degraded/offline</span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Open Alerts</div>
          <div
            className="stat-value"
            style={{ color: alertStats.open > 0 ? 'var(--color-error)' : 'var(--color-success)' }}
          >
            {alertStats.open.toLocaleString()}
          </div>
          <div className="stat-sub">
            {alertStats.open === 0
              ? 'all clear'
              : `${alertStats.critical.toLocaleString()} critical · ${alertStats.unacknowledged.toLocaleString()} unacknowledged`}
          </div>
        </div>
      </div>

      <div className="charts-row">
        <div className="card">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 8,
            }}
          >
            <div className="chart-title">Fleet Traffic · Aggregate Interface Throughput</div>
            <div style={{ display: 'flex', gap: 4 }}>
              {TIME_RANGES.map(({ label, hours }) => (
                <button
                  key={label}
                  onClick={() => setTrafficHours(hours)}
                  style={{
                    background: trafficHours === hours ? 'var(--color-accent)' : 'var(--color-bg)',
                    color: trafficHours === hours ? '#fff' : 'var(--color-text-muted)',
                    border: `1px solid ${trafficHours === hours ? 'var(--color-accent)' : 'var(--color-border)'}`,
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 11,
                    cursor: 'pointer',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {trafficSeries.length > 0 ? (
            <ResponsiveContainer width="100%" height={90}>
              <LineChart data={trafficSeries} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                  vertical={false}
                />
                <XAxis
                  dataKey="time"
                  tick={{
                    fontSize: 9,
                    fill: 'var(--color-text-faint)',
                    fontFamily: 'IBM Plex Mono',
                  }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis hide />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid var(--color-border)',
                    borderRadius: 4,
                    fontSize: 11,
                  }}
                  formatter={(v) => formatBps(v)}
                />
                <Line
                  type="monotone"
                  dataKey="in_bps"
                  name="In"
                  stroke="#2563eb"
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="out_bps"
                  name="Out"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div
              style={{
                height: 90,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span className="text-faint text-xs">No traffic data collected yet</span>
            </div>
          )}
        </div>

        <div className="card">
          <div className="chart-title">Device Status</div>
          <ResponsiveContainer width="100%" height={90}>
            <BarChart data={deviceStatusData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f24" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 9, fill: '#3f3f46', fontFamily: 'IBM Plex Mono' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis hide />
              <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={40}>
                {deviceStatusData.map((d) => (
                  <Cell key={d.label} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 8,
          }}
        >
          <div className="chart-title">Top Interfaces</div>
          <div style={{ display: 'flex', gap: 4 }}>
            {[
              ['top_by_traffic', 'By traffic'],
              ['top_by_utilization', 'By utilization'],
            ].map(([key, label]) => (
              <button
                key={key}
                className={`btn btn-sm ${topBy === key ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setTopBy(key)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {topRows.length === 0 ? (
          <span className="text-faint text-xs">No traffic data collected yet</span>
        ) : (
          <table className="table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Device</th>
                <th style={{ textAlign: 'left' }}>Interface</th>
                <th style={{ textAlign: 'right' }}>In</th>
                <th style={{ textAlign: 'right' }}>Out</th>
                <th style={{ textAlign: 'right' }}>Utilization</th>
              </tr>
            </thead>
            <tbody>
              {topRows.map((r) => (
                <tr key={`${r.device_ip}/${r.interface_name}`}>
                  <td>{r.device_name}</td>
                  <td>{r.interface_name}</td>
                  <td style={{ textAlign: 'right' }}>{formatBps(r.in_bps)}</td>
                  <td style={{ textAlign: 'right' }}>{formatBps(r.out_bps)}</td>
                  <td style={{ textAlign: 'right' }}>
                    {r.utilization_pct != null ? `${r.utilization_pct}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="detail-row">
        <div className="card">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 8,
            }}
          >
            <div className="chart-title">Active Alerts · {alertTotal.toLocaleString()}</div>
            <select
              className="input"
              aria-label="Filter alerts by severity"
              value={severityFilter}
              onChange={(e) => {
                setSeverityFilter(e.target.value);
                setAlertLimit(ALERT_PAGE_SIZE);
              }}
              style={{ width: 'auto', height: 24, fontSize: 11, padding: '0 4px' }}
            >
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
          {alerts.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 8 }}>
              <span style={{ color: 'var(--color-success)', fontSize: 14 }}>✓</span>
              <span className="text-faint text-xs">All clear</span>
            </div>
          ) : (
            alerts.map((alert) => {
              const sevColor =
                {
                  critical: 'var(--color-error)',
                  warning: 'var(--color-warning, #d97706)',
                  info: 'var(--color-text-faint)',
                }[alert.severity] || 'var(--color-error)';
              return (
                <div key={alert.id} className="agent-row">
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {alert.severity && (
                        <span
                          className="badge"
                          style={{
                            background: sevColor,
                            color: '#fff',
                            fontSize: 10,
                            textTransform: 'uppercase',
                            padding: '1px 6px',
                          }}
                        >
                          {alert.severity}
                        </span>
                      )}
                      <span className="agent-name" style={{ color: sevColor, fontSize: 12 }}>
                        {alert.alert_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="agent-meta">{alert.message}</div>
                    {canManageAlerts && (
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          marginTop: 6,
                          flexWrap: 'wrap',
                        }}
                      >
                        {alert.acknowledged_by_email ? (
                          <span className="badge badge-success" style={{ fontSize: 10 }}>
                            ✓ ack {alert.acknowledged_by_email}
                          </span>
                        ) : (
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleAck(alert)}
                          >
                            Acknowledge
                          </button>
                        )}
                        <select
                          className="input"
                          style={{ height: 24, fontSize: 11, padding: '0 4px', width: 'auto' }}
                          value={alert.assigned_to || ''}
                          onChange={(e) => handleAssign(alert, e.target.value)}
                        >
                          <option value="">Unassigned</option>
                          {assignableUsers.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.email}
                            </option>
                          ))}
                        </select>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => handleNote(alert)}
                        >
                          {alert.note ? 'Note ✎' : '+ Note'}
                        </button>
                        {alert.note && (
                          <span className="text-faint text-xs" title={alert.note}>
                            “{alert.note.length > 40 ? alert.note.slice(0, 40) + '…' : alert.note}”
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <span className="text-faint text-xs">
                    {Math.round((Date.now() - new Date(alert.triggered_at)) / 60000)}m ago
                  </span>
                </div>
              );
            })
          )}
          {alerts.length < alertTotal && (
            <button
              className="btn btn-sm btn-secondary"
              style={{ marginTop: 8 }}
              onClick={() => setAlertLimit((n) => n + ALERT_PAGE_SIZE)}
            >
              Show more ({(alertTotal - alerts.length).toLocaleString()} remaining)
            </button>
          )}
        </div>

        <div className="card">
          <div className="chart-title">Agent Status</div>
          {agents.length === 0 ? (
            <p className="text-faint text-xs" style={{ paddingTop: 8 }}>
              No agents registered.
            </p>
          ) : (
            [...agents]
              .sort((a, b) => {
                const order = { online: 0, degraded: 1, offline: 2 };
                return (order[a.status] ?? 3) - (order[b.status] ?? 3);
              })
              .map((agent) => (
                <div className="agent-row" key={agent.agent_id}>
                  <div>
                    <div className="agent-name">{agent.hostname || agent.agent_id}</div>
                    <div className="agent-meta">
                      {agent.ip} · {agent.agent_id?.slice(0, 12)}…
                    </div>
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
              <span className="event-text">
                System loaded — {dev.total.toLocaleString()} devices, {agents.length} agents
              </span>
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
