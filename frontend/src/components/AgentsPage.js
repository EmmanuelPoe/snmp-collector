import React, { useState, useEffect } from 'react';
import { getAgents, createAgentSlot, deleteAgentSlot, clearOfflineAgents } from '../services/api';

const STATUS_BADGE = {
  online:   'badge-success',
  degraded: 'badge-warning',
  offline:  'badge-danger',
  pending:  'badge-warning',
};

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState({ col: 'hostname', dir: 'asc' });
  const [modal, setModal] = useState(null); // null | 'form' | 'command'
  const [label, setLabel] = useState('');
  const [deployResult, setDeployResult] = useState(null);
  const [deploying, setDeploying] = useState(false);
  const [copied, setCopied] = useState(false);

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

  const handleDeploy = async (e) => {
    e.preventDefault();
    if (!label.trim()) return;
    setDeploying(true);
    try {
      const result = await createAgentSlot(label.trim());
      setDeployResult(result);
      setModal('command');
      loadAgents();
    } catch {
      setError('Failed to create agent slot.');
    } finally {
      setDeploying(false);
    }
  };

  const handleRevoke = async (slotId) => {
    try {
      await deleteAgentSlot(slotId);
      loadAgents();
    } catch {
      setError('Failed to revoke slot.');
    }
  };

  const handleClearOffline = async () => {
    try {
      await clearOfflineAgents();
      loadAgents();
    } catch {
      setError('Failed to clear offline agents.');
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(deployResult.install_command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const closeModal = () => {
    setModal(null);
    setLabel('');
    setDeployResult(null);
    setCopied(false);
  };

  const STATUS_ORDER = { online: 0, degraded: 1, pending: 2, offline: 3 };

  const filtered = agents
    .filter(a =>
      (a.hostname || '').toLowerCase().includes(search.toLowerCase()) ||
      (a.ip || '').includes(search)
    )
    .sort((a, b) => {
      const statusDiff = (STATUS_ORDER[a.status] ?? 4) - (STATUS_ORDER[b.status] ?? 4);
      if (statusDiff !== 0) return statusDiff;
      const valA = (a[sort.col] || '').toString().toLowerCase();
      const valB = (b[sort.col] || '').toString().toLowerCase();
      return sort.dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
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
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input table-search"
            type="search"
            placeholder="Search by hostname or IP…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button className="btn btn-secondary" onClick={handleClearOffline}>
            Clear Offline
          </button>
          <button className="btn btn-primary" onClick={() => setModal('form')}>
            Deploy Agent
          </button>
        </div>
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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 && !search ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No agents. Click <strong>Deploy Agent</strong> to provision one.
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No agents match "{search}"
                </td>
              </tr>
            ) : (
              filtered.map(agent => (
                <tr key={agent.agent_id}>
                  <td><code className="font-mono text-xs">{agent.agent_id?.slice(0, 16)}…</code></td>
                  <td>{agent.hostname}</td>
                  <td className="font-mono text-sm">{agent.ip || '—'}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[agent.status] || 'badge-info'}`}>
                      {agent.status}
                    </span>
                  </td>
                  <td className="text-sm text-muted">
                    {agent.last_seen ? new Date(agent.last_seen).toLocaleString() : '—'}
                  </td>
                  <td className="font-mono text-sm">
                    {agent.status === 'pending' ? '—' : agent.pending_uploads}
                  </td>
                  <td>
                    {agent.status === 'pending' && (
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleRevoke(agent.slot_id || agent.agent_id)}
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {modal === 'form' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Deploy Agent</div>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <form onSubmit={handleDeploy}>
              <div className="form-group">
                <label className="form-label">Agent Label</label>
                <input
                  className="input"
                  type="text"
                  placeholder="e.g. NYC datacenter"
                  value={label}
                  onChange={e => setLabel(e.target.value)}
                  autoFocus
                />
                <div className="form-hint">Used to identify this agent in the list.</div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={deploying || !label.trim()}>
                  {deploying ? 'Creating…' : 'Generate Install Command'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {modal === 'command' && deployResult && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" style={{ maxWidth: 600 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Install Command</div>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <div style={{ padding: '0 1.5rem 1rem' }}>
              <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
                Run this command on the target machine. The token expires in 24 hours.
              </p>
              <pre style={{
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: 6,
                padding: '12px 14px',
                fontSize: 12,
                fontFamily: "'IBM Plex Mono', monospace",
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                color: 'var(--color-text)',
              }}>
                {deployResult.install_command}
              </pre>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={closeModal}>Close</button>
              <button className="btn btn-primary" onClick={handleCopy}>
                {copied ? 'Copied!' : 'Copy Command'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
