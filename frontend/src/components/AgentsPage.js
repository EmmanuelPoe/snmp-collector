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

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Agents</div>
          <div className="page-subtitle">Distributed SNMP collection agents</div>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Agent ID</th>
              <th>Hostname</th>
              <th>IP</th>
              <th>Status</th>
              <th>Last Seen</th>
              <th>Pending Uploads</th>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                  No agents registered.
                </td>
              </tr>
            ) : (
              agents.map(agent => (
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
