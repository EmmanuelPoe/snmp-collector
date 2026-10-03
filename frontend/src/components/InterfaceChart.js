import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getInterfaceHistory } from '../services/api';

const TIME_RANGES = [
  { label: '1h', hours: 1, buckets: 60 },
  { label: '6h', hours: 6, buckets: 72 },
  { label: '24h', hours: 24, buckets: 96 },
  { label: '7d', hours: 168, buckets: 84 },
];

function formatBps(bps) {
  if (bps == null) return '—';
  if (bps >= 1e9) return `${(bps / 1e9).toFixed(1)} Gbps`;
  if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)} Mbps`;
  if (bps >= 1e3) return `${(bps / 1e3).toFixed(1)} Kbps`;
  return `${bps.toFixed(0)} bps`;
}

function formatLabel(iso, hours) {
  if (!iso) return '';
  const d = new Date(iso);
  if (hours <= 24) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const CHART_STYLE = {
  background: 'var(--color-bg-elevated)',
  border: '1px solid var(--color-border)',
  borderRadius: 6,
};

const TOOLTIP_STYLE = {
  background: 'var(--color-bg-elevated)',
  border: '1px solid var(--chart-tooltip-border)',
  borderRadius: 6,
  fontSize: 11,
};

export default function InterfaceChart({ deviceId, interfaceName }) {
  const [range, setRange] = useState(TIME_RANGES[0]);
  const [series, setSeries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await getInterfaceHistory(deviceId, interfaceName, range.hours, range.buckets);
      setSeries(
        (data.series || []).map((p) => ({
          ...p,
          label: formatLabel(p.timestamp, range.hours),
        })),
      );
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [deviceId, interfaceName, range]);

  useEffect(() => {
    load();
  }, [load]);

  const hasErrors = series.some((p) => p.in_errors || p.out_errors);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 4, marginBottom: 6 }}>
        {TIME_RANGES.map((r) => (
          <button
            key={r.label}
            onClick={(e) => {
              e.stopPropagation();
              setRange(r);
            }}
            style={{
              background:
                range.label === r.label
                  ? 'color-mix(in srgb, var(--color-accent) 20%, transparent)'
                  : 'transparent',
              border: `1px solid ${range.label === r.label ? 'var(--color-accent)' : 'var(--color-border)'}`,
              color: range.label === r.label ? 'var(--color-accent)' : 'var(--color-text-muted)',
              borderRadius: 4,
              padding: '1px 7px',
              fontSize: 10,
              cursor: 'pointer',
            }}
          >
            {r.label}
          </button>
        ))}
      </div>

      {loading && (
        <div
          style={{
            height: 88,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--chart-axis)',
            fontSize: 11,
          }}
        >
          Loading…
        </div>
      )}
      {!loading && error && (
        <div
          style={{
            height: 88,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-error)',
            fontSize: 11,
          }}
        >
          Failed to load chart data
        </div>
      )}
      {!loading && !error && (
        <>
          <div style={{ ...CHART_STYLE, marginBottom: 4 }}>
            <ResponsiveContainer width="100%" height={88}>
              <AreaChart data={series} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={`gIn_${interfaceName}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--chart-in)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--chart-in)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id={`gOut_${interfaceName}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--chart-out)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--chart-out)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 9, fill: 'var(--chart-axis)' }}
                  interval="preserveStartEnd"
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={(v) => formatBps(v)}
                  tick={{ fontSize: 9, fill: 'var(--chart-axis)' }}
                  width={55}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(v, name) => [formatBps(v), name]}
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: 'var(--color-text-secondary)' }}
                />
                <Legend wrapperStyle={{ fontSize: 10, paddingTop: 2 }} />
                <Area
                  type="monotone"
                  dataKey="in_bps"
                  name="In"
                  stroke="var(--chart-in)"
                  fill={`url(#gIn_${interfaceName})`}
                  dot={false}
                  connectNulls
                  strokeWidth={1.5}
                />
                <Area
                  type="monotone"
                  dataKey="out_bps"
                  name="Out"
                  stroke="var(--chart-out)"
                  fill={`url(#gOut_${interfaceName})`}
                  dot={false}
                  connectNulls
                  strokeWidth={1.5}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {hasErrors && (
            <div style={CHART_STYLE}>
              <ResponsiveContainer width="100%" height={48}>
                <AreaChart data={series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 9, fill: 'var(--chart-axis)' }}
                    interval="preserveStartEnd"
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'var(--chart-axis)' }}
                    width={30}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    labelStyle={{ color: 'var(--color-text-secondary)' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="in_errors"
                    name="In Errors"
                    stroke="var(--color-error)"
                    fill="color-mix(in srgb, var(--color-error) 12%, transparent)"
                    dot={false}
                    connectNulls
                    strokeWidth={1}
                  />
                  <Area
                    type="monotone"
                    dataKey="out_errors"
                    name="Out Errors"
                    stroke="var(--chart-err-2)"
                    fill="color-mix(in srgb, var(--chart-err-2) 12%, transparent)"
                    dot={false}
                    connectNulls
                    strokeWidth={1}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
