import React, { useState, useEffect } from 'react';
import { getAgents } from '../services/api';

const STATUS_COLORS = {
    online: 'success',
    degraded: 'warning',
    offline: 'danger',
};

function AgentsPage() {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadAgents();
        const interval = setInterval(loadAgents, 30000);
        return () => clearInterval(interval);
    }, []);

    const loadAgents = async () => {
        try {
            const data = await getAgents();
            setAgents(data);
            setError(null);
        } catch (err) {
            setError('Unable to reach manager. Is it running?');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="container" style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                <div className="spinner"></div>
            </div>
        );
    }

    return (
        <div className="container">
            <div className="page-header">
                <h1>Agents</h1>
                <p>Distributed SNMP collection agents</p>
            </div>

            {error && (
                <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
                    {error}
                </div>
            )}

            <div className="glass-card">
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
                                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-muted)' }}>
                                    No agents registered.
                                </td>
                            </tr>
                        ) : (
                            agents.map(agent => (
                                <tr key={agent.agent_id}>
                                    <td><code>{agent.agent_id}</code></td>
                                    <td>{agent.hostname}</td>
                                    <td>{agent.ip}</td>
                                    <td>
                                        <span className={`badge badge-${STATUS_COLORS[agent.status] || 'secondary'}`}>
                                            {agent.status}
                                        </span>
                                    </td>
                                    <td>
                                        {agent.last_seen
                                            ? new Date(agent.last_seen).toLocaleString()
                                            : '—'}
                                    </td>
                                    <td>{agent.pending_uploads}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default AgentsPage;
