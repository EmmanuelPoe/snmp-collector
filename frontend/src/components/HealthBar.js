import React from 'react';

// Proportional status bar. A plain bar chart hides small-but-critical counts
// (24 down next to 1,895 up is a sliver), so every non-zero segment gets a
// minimum visible width and the exact numbers are always listed beside it.
const MIN_SEGMENT_PCT = 1.5;

export default function HealthBar({ segments }) {
  const total = segments.reduce((n, s) => n + s.count, 0);
  // Floor tiny segments so they stay visible, then renormalise so the bases sum
  // to exactly 100% (otherwise the last segment overflows and is clipped).
  const shown = segments.filter((s) => s.count > 0);
  const floored = shown.map((s) => Math.max((s.count / total) * 100, MIN_SEGMENT_PCT));
  const flooredSum = floored.reduce((n, w) => n + w, 0);
  const label = segments
    .map((s) => `${s.count.toLocaleString()} ${s.label.toLowerCase()}`)
    .join(', ');

  return (
    <div>
      {total === 0 ? (
        <div className="health-bar health-bar-empty" role="img" aria-label="No devices" />
      ) : (
        <div className="health-bar" role="img" aria-label={label}>
          {shown.map((s, i) => (
            <div
              key={s.label}
              className="health-bar-segment"
              style={{ flexBasis: `${(floored[i] / flooredSum) * 100}%`, background: s.color }}
              title={`${s.label}: ${s.count.toLocaleString()}`}
            />
          ))}
        </div>
      )}
      <ul className="health-legend">
        {segments.map((s) => (
          <li key={s.label}>
            <span className="health-swatch" style={{ background: s.color }} />
            <span className="health-legend-label">{s.label}</span>
            <span className="health-legend-count">{s.count.toLocaleString()}</span>
            <span className="health-legend-pct">
              {total ? `${((s.count / total) * 100).toFixed(1)}%` : '—'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
