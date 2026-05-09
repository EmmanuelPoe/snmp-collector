import React, { useState, useEffect } from 'react';
import { getAgents } from '../services/api';

const STATUS_BADGE = {
  online:   'badge-success',
  degraded: 'badge-warning',
  offline:  'badge-danger',
};

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState({ col: 'hostname', dir: 'asc' });

  useEffect(() => {
    loadAgents();
    const iv = setInterval(loadAgents, 30000);
    return () => clearInterval(iv);
  }, []);

  const loadAgents = async () => {
    try {
      const data = await getAgents();
      setAgents(data);
      setError(null);
    } catch {
      setError('Unable to reach manager. Is it running?');
    } finally {
      setLoading(false);
    }
  };

  const filtered = agents
    .filter(a =>
      (a.hostname || '').toLowerCase().includes(search.toLowerCase()) ||
      (a.ip || '').includes(search)
    )
    .sort((a, b) => {
      const valA = (a[sort.col] || '').toString().toLowerCase();
      const valB = (b[sort.col] || '').toString().toLowerCase();
      return sort.dir === 'asc'
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    });

  function toggleSort(col) {
    setSort(prev => ({ col, dir: prev.col === col && prev.dir === 'asc' ? 'desc' : 'asc' }));
  }
  function sortIndicator(col) {
    if (sort.col !== col) return '';
    return sort.dir === 'asc' ? ' ↑' : ' ↓';
  }

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Agents</div>
          <div className="page-subtitle">Distributed SNMP collection agents</div>
        </div>
        <input
          className="input table-search"
          type="search"
          placeholder="Search by hostname or IP…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Agent ID</th>
              <th className="sortable" onClick={() => toggleSort('hostname')}>Hostname{sortIndicator('hostname')}</th>
              <th className="sortable" onClick={() => toggleSort('ip')}>IP{sortIndicator('ip')}</th>
              <th className="sortable" onClick={() => toggleSort('status')}>Status{sortIndicator('status')}</th>
              <th>Last Seen</th>
              <th>Pending Uploads</th>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 && !search ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No agents registered.
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No agents match "{search}"
                </td>
              </tr>
            ) : (
              filtered.map(agent => (
                <tr key={agent.agent_id}>
                  <td><code className="font-mono text-xs">{agent.agent_id}</code></td>
                  <td>{agent.hostname}</td>
                  <td className="font-mono text-sm">{agent.ip}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[agent.status] || 'badge-info'}`}>
                      {agent.status}
                    </span>
                  </td>
                  <td className="text-sm text-muted">
                    {agent.last_seen ? new Date(agent.last_seen).toLocaleString() : '—'}
                  </td>
                  <td className="font-mono text-sm">{agent.pending_uploads}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
