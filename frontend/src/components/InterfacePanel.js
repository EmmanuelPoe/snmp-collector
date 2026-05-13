import React, { useState, useEffect } from 'react';
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getMetrics } from '../services/api';

const TIME_RANGES = [
    { label: '1h', hours: 1 },
    { label: '6h', hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d', hours: 168 },
];

function formatBps(bps) {
    if (bps === null || bps === undefined) return 'N/A';
    if (bps >= 1e9) return (bps / 1e9).toFixed(2) + ' Gbps';
    if (bps >= 1e6) return (bps / 1e6).toFixed(2) + ' Mbps';
    if (bps >= 1e3) return (bps / 1e3).toFixed(2) + ' Kbps';
    return bps.toFixed(0) + ' bps';
}

function computeDeltas(rows) {
    const byOid = {};
    for (const row of rows) {
        if (!byOid[row.oid_name]) byOid[row.oid_name] = [];
        byOid[row.oid_name].push({ ts: new Date(row.timestamp).getTime(), value: Number(row.value) });
    }
    for (const oid of Object.keys(byOid)) {
        byOid[oid].sort((a, b) => a.ts - b.ts);
    }
    function deltas(pts) {
        const result = [];
        for (let i = 1; i < pts.length; i++) {
            const dt = (pts[i].ts - pts[i - 1].ts) / 1000;
            if (dt <= 0) continue;
            const dv = Math.max(0, pts[i].value - pts[i - 1].value);
            result.push({ ts: pts[i].ts, rate: dv / dt });
        }
        return result;
    }
    const inOctets  = deltas(byOid['ifHCInOctets']  || byOid['ifInOctets']   || []);
    const outOctets = deltas(byOid['ifHCOutOctets'] || byOid['ifOutOctets']  || []);
    const inErrors  = deltas(byOid['ifInErrors']   || []);
    const outErrors = deltas(byOid['ifOutErrors']  || []);
    const inDisc    = deltas(byOid['ifInDiscards'] || []);
    const outDisc   = deltas(byOid['ifOutDiscards']|| []);
    const refPts = inOctets.length >= outOctets.length ? inOctets : outOctets;
    function nearest(arr, ts) {
        const pt = arr.find(p => Math.abs(p.ts - ts) < 5000);
        return pt ? pt.rate : 0;
    }
    return refPts.map(pt => {
        const d = new Date(pt.ts);
        return {
            timeLabel: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            in_bps: pt.rate * 8,
            out_bps: nearest(outOctets, pt.ts) * 8,
            in_errors: nearest(inErrors, pt.ts),
            out_errors: nearest(outErrors, pt.ts),
            in_discards: nearest(inDisc, pt.ts),
            out_discards: nearest(outDisc, pt.ts),
        };
    });
}

const CHART_STYLE = { backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 };
const GRID = 'rgba(255,255,255,0.05)';
const AXIS = '#64748b';

function InterfacePanel({ deviceId, iface, ifaceData, onClose }) {
    const [timeRange, setTimeRange] = useState(1);
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadChartData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [deviceId, iface, timeRange]);

    const loadChartData = async () => {
        setLoading(true);
        try {
            const end = new Date();
            const start = new Date(end.getTime() - timeRange * 3600 * 1000);
            const rows = await getMetrics({ device_id: deviceId, interface_name: iface, start_time: start.toISOString(), end_time: end.toISOString(), limit: 10000 });
            setChartData(computeDeltas(rows));
        } catch (err) {
            console.error('InterfacePanel: failed to load chart data', err);
        } finally {
            setLoading(false);
        }
    };

    const currentInBps  = ifaceData?.current_in_bps  ?? 0;
    const currentOutBps = ifaceData?.current_out_bps ?? 0;
    const util          = ifaceData?.utilization_pct;
    const hasErrors = chartData.some(d => d.in_errors > 0 || d.out_errors > 0 || d.in_discards > 0 || d.out_discards > 0);

    return (
        <div style={{ width: 480, background: '#1a2035', borderLeft: '1px solid #334155', display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'hidden' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid #334155', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{iface}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>{(ifaceData?.status ?? 'unknown').toUpperCase()}{ifaceData?.speed_bps ? ` · ${formatBps(ifaceData.speed_bps)}` : ''}</div>
                </div>
                <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: '2px 6px', borderRadius: 4, lineHeight: 1 }}>✕</button>
            </div>
            <div style={{ padding: '8px 16px', borderBottom: '1px solid #1e293b', display: 'flex', gap: 6, flexShrink: 0 }}>
                {TIME_RANGES.map(({ label, hours }) => (
                    <button key={label} onClick={() => setTimeRange(hours)} style={{ background: timeRange === hours ? '#3b82f6' : '#1e293b', border: `1px solid ${timeRange === hours ? '#3b82f6' : '#334155'}`, color: timeRange === hours ? '#fff' : '#94a3b8', padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer' }}>{label}</button>
                ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, padding: '10px 16px', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
                {[
                    { val: formatBps(currentInBps), lbl: 'In (current)', color: '#3b82f6' },
                    { val: formatBps(currentOutBps), lbl: 'Out (current)', color: '#10b981' },
                    { val: util != null ? `${util}%` : '—', lbl: 'Utilization', color: (util ?? 0) >= 80 ? '#ef4444' : '#f59e0b' },
                ].map(({ val, lbl, color }) => (
                    <div key={lbl} style={{ background: '#0f172a', borderRadius: 6, padding: '8px 10px' }}>
                        <div style={{ fontSize: 15, fontWeight: 700, color }}>{val}</div>
                        <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>{lbl}</div>
                    </div>
                ))}
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>Loading...</div>
                ) : chartData.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>No data for this time range.</div>
                ) : (
                    <>
                        <div style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Network Traffic (bps)</div>
                            <ResponsiveContainer width="100%" height={160}>
                                <AreaChart data={chartData}>
                                    <defs>
                                        <linearGradient id="gradIn" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="gradOut" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                                    <XAxis dataKey="timeLabel" stroke={AXIS} fontSize={10} />
                                    <YAxis stroke={AXIS} fontSize={10} tickFormatter={v => formatBps(v)} width={72} />
                                    <Tooltip contentStyle={CHART_STYLE} formatter={(v, name) => [formatBps(v), name]} />
                                    <Legend iconType="circle" />
                                    <Area type="monotone" dataKey="in_bps" stroke="#3b82f6" fill="url(#gradIn)" name="In" dot={false} strokeWidth={2} />
                                    <Area type="monotone" dataKey="out_bps" stroke="#10b981" fill="url(#gradOut)" name="Out" dot={false} strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                        {hasErrors && (
                            <div style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Errors &amp; Discards</div>
                                <ResponsiveContainer width="100%" height={120}>
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                                        <XAxis dataKey="timeLabel" stroke={AXIS} fontSize={10} />
                                        <YAxis stroke={AXIS} fontSize={10} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Legend iconType="circle" />
                                        <Line type="monotone" dataKey="in_errors" stroke="#ef4444" dot={false} name="In Errors" strokeWidth={1.5} />
                                        <Line type="monotone" dataKey="out_errors" stroke="#f97316" dot={false} name="Out Errors" strokeWidth={1.5} />
                                        <Line type="monotone" dataKey="in_discards" stroke="#f59e0b" dot={false} name="In Discards" strokeWidth={1.5} />
                                        <Line type="monotone" dataKey="out_discards" stroke="#eab308" dot={false} name="Out Discards" strokeWidth={1.5} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

export default InterfacePanel;
