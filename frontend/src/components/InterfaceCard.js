import React from 'react';
import InterfaceChart from './InterfaceChart';

function formatBps(bps) {
  if (bps === null || bps === undefined) return '—';
  if (bps >= 1e9) return (bps / 1e9).toFixed(1) + ' Gbps';
  if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' Mbps';
  if (bps >= 1e3) return (bps / 1e3).toFixed(1) + ' Kbps';
  return bps.toFixed(0) + ' bps';
}

function InterfaceCard({ deviceId, iface, data, isActive, onClick }) {
  const isDown = data.status === 'down';
  const highUtil = data.utilization_pct != null && data.utilization_pct >= 80;
  return (
    <div
      onClick={onClick}
      style={{
        background: isActive ? 'var(--color-accent-dim)' : 'var(--color-bg-elevated)',
        border: `1px solid ${isActive ? 'var(--color-accent)' : 'var(--color-border)'}`,
        boxShadow: isActive
          ? '0 0 0 2px color-mix(in srgb, var(--color-accent) 25%, transparent)'
          : 'none',
        borderRadius: 10,
        padding: 14,
        cursor: 'pointer',
        opacity: isDown ? 0.6 : 1,
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 10,
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--color-text-primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {iface}
          </div>
          {data.alias && (
            <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>
              {data.alias}
            </div>
          )}
        </div>
        <span
          style={{
            fontSize: 10,
            padding: '2px 7px',
            borderRadius: 10,
            fontWeight: 600,
            whiteSpace: 'nowrap',
            marginLeft: 8,
            background: isDown
              ? 'color-mix(in srgb, var(--color-error) 16%, transparent)'
              : 'color-mix(in srgb, var(--color-success) 16%, transparent)',
            color: isDown ? 'var(--color-error)' : 'var(--color-success)',
            border: `1px solid ${isDown ? 'color-mix(in srgb, var(--color-error) 32%, transparent)' : 'color-mix(in srgb, var(--color-success) 32%, transparent)'}`,
          }}
        >
          {(data.status ?? 'unknown').toUpperCase()}
          {data.speed_bps && !isDown ? ` · ${formatBps(data.speed_bps)}` : ''}
        </span>
      </div>
      <div style={{ marginBottom: 10 }} onClick={(e) => e.stopPropagation()}>
        <InterfaceChart deviceId={deviceId} interfaceName={iface} />
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr 1fr',
          gap: 6,
          textAlign: 'center',
        }}
      >
        {[
          { val: formatBps(data.current_in_bps), lbl: 'In', color: 'var(--chart-in)' },
          { val: formatBps(data.current_out_bps), lbl: 'Out', color: 'var(--chart-out)' },
          {
            val: data.utilization_pct != null ? `${data.utilization_pct}%` : '—',
            lbl: 'Util',
            color: highUtil ? 'var(--color-error)' : 'var(--chart-warn)',
          },
          {
            val: data.error_count ?? 0,
            lbl: 'Errors',
            color: (data.error_count ?? 0) > 0 ? 'var(--color-error)' : 'var(--color-text-muted)',
          },
        ].map(({ val, lbl, color }) => (
          <div key={lbl}>
            <div style={{ fontSize: 12, fontWeight: 600, color }}>{val}</div>
            <div
              style={{
                fontSize: 9,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                marginTop: 1,
              }}
            >
              {lbl}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default InterfaceCard;
