import React, { useState, useEffect, useCallback } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid,
    Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { getInterfaceHistory } from '../services/api';

const TIME_RANGES = [
    { label: '1h',  hours: 1,   buckets: 60 },
    { label: '6h',  hours: 6,   buckets: 72 },
    { label: '24h', hours: 24,  buckets: 96 },
    { label: '7d',  hours: 168, buckets: 84 },
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
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const CHART_STYLE = {
    background: 'rgba(0,0,0,0.2)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 6,
};

const TOOLTIP_STYLE = {
    background: '#1e293b',
    border: '1px solid rgba(255,255,255,0.1)',
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
                (data.series || []).map(p => ({
                    ...p,
                    label: formatLabel(p.timestamp, range.hours),
                }))
            );
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    }, [deviceId, interfaceName, range]);

    useEffect(() => { load(); }, [load]);

    const hasErrors = series.some(p => p.in_errors || p.out_errors);

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 4, marginBottom: 6 }}>
                {TIME_RANGES.map(r => (
                    <button
                        key={r.label}
                        onClick={e => { e.stopPropagation(); setRange(r); }}
                        style={{
                            background: range.label === r.label ? 'rgba(59,130,246,0.3)' : 'transparent',
                            border: `1px solid ${range.label === r.label ? '#3b82f6' : 'rgba(255,255,255,0.1)'}`,
                            color: range.label === r.label ? '#93c5fd' : '#64748b',
                            borderRadius: 4, padding: '1px 7px', fontSize: 10, cursor: 'pointer',
                        }}
                    >
                        {r.label}
                    </button>
                ))}
            </div>

            {loading && (
                <div style={{ height: 88, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#475569', fontSize: 11 }}>
                    Loading…
                </div>
            )}
            {!loading && error && (
                <div style={{ height: 88, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444', fontSize: 11 }}>
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
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id={`gOut_${interfaceName}`} x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                                <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#475569' }} interval="preserveStartEnd" tickLine={false} axisLine={false} />
                                <YAxis tickFormatter={formatBps} tick={{ fontSize: 9, fill: '#475569' }} width={55} tickLine={false} axisLine={false} />
                                <Tooltip formatter={(v, name) => [formatBps(v), name]} contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#94a3b8' }} />
                                <Legend wrapperStyle={{ fontSize: 10, paddingTop: 2 }} />
                                <Area type="monotone" dataKey="in_bps" name="In" stroke="#3b82f6" fill={`url(#gIn_${interfaceName})`} dot={false} connectNulls strokeWidth={1.5} />
                                <Area type="monotone" dataKey="out_bps" name="Out" stroke="#10b981" fill={`url(#gOut_${interfaceName})`} dot={false} connectNulls strokeWidth={1.5} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {hasErrors && (
                        <div style={CHART_STYLE}>
                            <ResponsiveContainer width="100%" height={48}>
                                <AreaChart data={series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                                    <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#475569' }} interval="preserveStartEnd" tickLine={false} axisLine={false} />
                                    <YAxis tick={{ fontSize: 9, fill: '#475569' }} width={30} tickLine={false} axisLine={false} />
                                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#94a3b8' }} />
                                    <Area type="monotone" dataKey="in_errors" name="In Errors" stroke="#ef4444" fill="rgba(239,68,68,0.1)" dot={false} connectNulls strokeWidth={1} />
                                    <Area type="monotone" dataKey="out_errors" name="Out Errors" stroke="#f97316" fill="rgba(249,115,22,0.1)" dot={false} connectNulls strokeWidth={1} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
