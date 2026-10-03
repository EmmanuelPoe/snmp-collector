export function formatBps(bps, digits) {
  if (bps == null) return '—';
  const d = (dflt) => digits ?? dflt;
  if (bps >= 1e9) return (bps / 1e9).toFixed(d(2)) + ' Gbps';
  if (bps >= 1e6) return (bps / 1e6).toFixed(d(1)) + ' Mbps';
  if (bps >= 1e3) return (bps / 1e3).toFixed(d(1)) + ' kbps';
  return Math.round(bps) + ' bps';
}
