import React, { useState, useEffect } from 'react';
import { getDevices, getMetrics, healthCheck } from '../services/api';
import { Link } from 'react-router-dom';

function Dashboard() {
    const [stats, setStats] = useState({
        totalDevices: 0,
        activeDevices: 0,
        metrics: 0,
        status: 'loading'
    });
    const [recentMetrics, setRecentMetrics] = useState([]);

    useEffect(() => {
        loadDashboardData();
    }, []);

    const loadDashboardData = async () => {
        try {
            const [devices, metrics, health] = await Promise.all([
                getDevices(),
                getMetrics({ limit: 10 }),
                healthCheck()
            ]);

            setStats({
                totalDevices: devices.length,
                activeDevices: devices.filter(d => d.enabled).length,
                metrics: metrics.length,
                status: health.status
            });

            setRecentMetrics(metrics.slice(0, 5));
        } catch (error) {
            console.error('Error loading dashboard:', error);
            setStats(prev => ({ ...prev, status: 'error' }));
        }
    };

    return (
        <div className="container">
            <div className="page-header">
                <h1>Dashboard</h1>
                <p>Overview of your SNMP metrics collection system</p>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                <div className="stat-card fade-in">
                    <div className="stat-label">Total Devices</div>
                    <div className="stat-value">{stats.totalDevices}</div>
                </div>
                <div className="stat-card fade-in" style={{ animationDelay: '0.1s' }}>
                    <div className="stat-label">Active Devices</div>
                    <div className="stat-value">{stats.activeDevices}</div>
                </div>
                <div className="stat-card fade-in" style={{ animationDelay: '0.2s' }}>
                    <div className="stat-label">Recent Metrics</div>
                    <div className="stat-value">{stats.metrics}</div>
                </div>
                <div className="stat-card fade-in" style={{ animationDelay: '0.3s' }}>
                    <div className="stat-label">System Status</div>
                    <div className="stat-value" style={{ fontSize: '1.5rem' }}>
                        <span className={`badge badge-${stats.status === 'healthy' ? 'success' : 'danger'}`}>
                            {stats.status}
                        </span>
                    </div>
                </div>
            </div>

            {/* Quick Actions */}
            <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                <h3>Quick Actions</h3>
                <div className="flex gap-md" style={{ marginTop: 'var(--spacing-lg)' }}>
                    <Link to="/devices">
                        <button className="btn btn-primary">Manage Devices</button>
                    </Link>
                    <Link to="/metrics">
                        <button className="btn btn-secondary">View Metrics</button>
                    </Link>
                    <Link to="/config">
                        <button className="btn btn-secondary">Configuration</button>
                    </Link>
                </div>
            </div>

            {/* Recent Metrics */}
            {recentMetrics.length > 0 && (
                <div className="glass-card">
                    <h3>Recent Metrics</h3>
                    <table className="data-table" style={{ marginTop: 'var(--spacing-lg)' }}>
                        <thead>
                            <tr>
                                <th>Device ID</th>
                                <th>Interface</th>
                                <th>OID Name</th>
                                <th>Value</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>
                            {recentMetrics.map((metric, index) => (
                                <tr key={index}>
                                    <td>{metric.device_id}</td>
                                    <td>{metric.interface_name || 'N/A'}</td>
                                    <td>{metric.oid_name || metric.oid}</td>
                                    <td>{metric.value !== null ? metric.value.toFixed(2) : 'N/A'}</td>
                                    <td className="text-sm text-muted">
                                        {new Date(metric.timestamp).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

export default Dashboard;
