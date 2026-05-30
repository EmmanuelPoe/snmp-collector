import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getTraps, getDevices } from '../services/api';

const TIME_RANGES = [
    { label: '1h',  hours: 1 },
    { label: '6h',  hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d',  hours: 168 },
];

function trapKey(t) {
    return `${t.received_at}:${t.device_ip}:${t.trap_oid}`;
}

export default function TrapsPage() {
    const [traps, setTraps] = useState([]);
    const [newKeys, setNewKeys] = useState(new Set());
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [hours, setHours] = useState(24);
    const [deviceFilter, setDeviceFilter] = useState('');
    const [oidFilter, setOidFilter] = useState('');
    const prevKeys = useRef(null);

    useEffect(() => {
        getDevices().then(setDevices).catch(() => {});
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = { hours, limit: 200 };
            if (deviceFilter) params.device_id = deviceFilter;
            if (oidFilter) params.trap_oid = oidFilter;
            const data = await getTraps(params);
            const keys = new Set(data.map(trapKey));
            if (prevKeys.current !== null) {
                setNewKeys(new Set([...keys].filter(k => !prevKeys.current.has(k))));
            }
            prevKeys.current = keys;
            setTraps(data);
        } catch {
            // non-fatal
        } finally {
            setLoading(false);
        }
    }, [hours, deviceFilter, oidFilter]);

    useEffect(() => {
        load();
        const iv = setInterval(load, 30000);
        return () => clearInterval(iv);
    }, [load]);

    const deviceName = (ip) => {
        const d = devices.find(d => d.ip_address === ip);
        return d ? d.name : ip;
    };

    const rangeLabel = hours === 1 ? '1 hour' : hours < 24 ? `${hours} hours` : hours === 24 ? '24 hours' : '7 days';

    return (
        <div className="fade-in">
            <div className="page-header">
                <div>
                    <div className="page-title">SNMP Traps</div>
                    <div className="page-subtitle">Incoming trap events from devices</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                        className="input table-search"
                        type="search"
                        placeholder="Filter by OID…"
                        value={oidFilter}
                        onChange={e => setOidFilter(e.target.value)}
                    />
                    <select
                        className="input"
                        value={deviceFilter}
                        onChange={e => setDeviceFilter(e.target.value)}
                        style={{ width: 'auto' }}
                    >
                        <option value="">All devices</option>
                        {devices.map(d => (
                            <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                    </select>
                    <div style={{ display: 'flex', gap: 4 }}>
                        {TIME_RANGES.map(r => (
                            <button
                                key={r.label}
                                onClick={() => setHours(r.hours)}
                                style={{
                                    background: hours === r.hours ? 'var(--color-accent)' : 'var(--color-bg)',
                                    color: hours === r.hours ? '#fff' : 'var(--color-text-muted)',
                                    border: `1px solid ${hours === r.hours ? 'var(--color-accent)' : 'var(--color-border)'}`,
                                    padding: '2px 8px', borderRadius: 4, fontSize: 11, cursor: 'pointer',
                                }}
                            >
                                {r.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Received</th>
                            <th>Device</th>
                            <th>Trap OID</th>
                            <th>Varbinds</th>
                            <th>Agent</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && (
                            <tr>
                                <td colSpan="5" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                                    Loading…
                                </td>
                            </tr>
                        )}
                        {!loading && traps.length === 0 && (
                            <tr>
                                <td colSpan="5" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                                    No traps received in the last {rangeLabel}.
                                    {' '}Enable <code>TRAP_ENABLED=true</code> on the agent to start receiving traps.
                                </td>
                            </tr>
                        )}
                        {!loading && traps.map((trap, i) => (
                            <tr key={i} className={newKeys.has(trapKey(trap)) ? 'trap-new' : ''}>
                                <td className="font-mono text-sm text-muted">
                                    {new Date(trap.received_at).toLocaleString()}
                                </td>
                                <td>{deviceName(trap.device_ip)}</td>
                                <td className="font-mono text-xs">{trap.trap_oid}</td>
                                <td>
                                    <details>
                                        <summary style={{ cursor: 'pointer', fontSize: 11, color: 'var(--color-text-muted)' }}>
                                            {Object.keys(JSON.parse(trap.varbinds || '{}')).length} vars
                                        </summary>
                                        <pre style={{ fontSize: 10, marginTop: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--color-text-faint)' }}>
                                            {JSON.stringify(JSON.parse(trap.varbinds || '{}'), null, 2)}
                                        </pre>
                                    </details>
                                </td>
                                <td className="font-mono text-xs text-muted">{trap.agent_id?.slice(0, 14)}…</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
