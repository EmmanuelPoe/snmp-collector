export function formatBps(bps) {
  if (bps == null) return '—';
  if (bps >= 1e9) return (bps / 1e9).toFixed(2) + ' Gbps';
  if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' Mbps';
  if (bps >= 1e3) return (bps / 1e3).toFixed(1) + ' kbps';
  return Math.round(bps) + ' bps';
}
