import React from 'react';

function formatBps(bps) {
    if (bps === null || bps === undefined) return '—';
    if (bps >= 1e9) return (bps / 1e9).toFixed(1) + ' Gbps';
    if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' Mbps';
    if (bps >= 1e3) return (bps / 1e3).toFixed(1) + ' Kbps';
    return bps.toFixed(0) + ' bps';
}

function Sparkline({ sparkline }) {
    if (!sparkline || sparkline.length === 0) {
        return <div style={{ height: 48, background: 'rgba(0,0,0,0.2)', borderRadius: 4 }} />;
    }
    const maxVal = Math.max(...sparkline.map(p => Math.max(p.in_bps, p.out_bps)), 1);
    return (
        <div style={{ height: 48, display: 'flex', alignItems: 'flex-end', gap: 1, background: 'rgba(0,0,0,0.2)', borderRadius: 4, padding: 2, overflow: 'hidden' }}>
            {sparkline.map((pt, i) => (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}>
                    <div style={{ background: 'rgba(59,130,246,0.7)', height: `${Math.max((pt.in_bps / maxVal) * 100, 1)}%`, borderRadius: '1px 1px 0 0' }} />
                </div>
            ))}
        </div>
    );
}

function InterfaceCard({ iface, data, isActive, onClick }) {
    const isDown = data.status === 'down';
    const highUtil = data.utilization_pct != null && data.utilization_pct >= 80;
    return (
        <div onClick={onClick} style={{ background: isActive ? '#1a2744' : '#1e293b', border: `1px solid ${isActive ? '#3b82f6' : '#334155'}`, boxShadow: isActive ? '0 0 0 2px rgba(59,130,246,0.25)' : 'none', borderRadius: 10, padding: 14, cursor: 'pointer', opacity: isDown ? 0.6 : 1, transition: 'border-color 0.15s, box-shadow 0.15s' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{iface}</div>
                    {data.alias && <div style={{ fontSize: 10, color: '#64748b', marginTop: 1 }}>{data.alias}</div>}
                </div>
                <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 10, fontWeight: 600, whiteSpace: 'nowrap', marginLeft: 8, background: isDown ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)', color: isDown ? '#ef4444' : '#10b981', border: `1px solid ${isDown ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}` }}>
                    {(data.status ?? 'unknown').toUpperCase()}
                    {data.speed_bps && !isDown ? ` · ${formatBps(data.speed_bps)}` : ''}
                </span>
            </div>
            <div style={{ marginBottom: 10 }}><Sparkline sparkline={data.sparkline} /></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 6, textAlign: 'center' }}>
                {[
                    { val: formatBps(data.current_in_bps), lbl: 'In', color: '#3b82f6' },
                    { val: formatBps(data.current_out_bps), lbl: 'Out', color: '#10b981' },
                    { val: data.utilization_pct != null ? `${data.utilization_pct}%` : '—', lbl: 'Util', color: highUtil ? '#ef4444' : '#f59e0b' },
                    { val: data.error_count ?? 0, lbl: 'Errors', color: (data.error_count ?? 0) > 0 ? '#ef4444' : '#64748b' },
                ].map(({ val, lbl, color }) => (
                    <div key={lbl}>
                        <div style={{ fontSize: 12, fontWeight: 600, color }}>{val}</div>
                        <div style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 1 }}>{lbl}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default InterfaceCard;
