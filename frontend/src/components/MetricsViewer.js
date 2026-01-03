import React, { useState, useEffect } from 'react';
import { getDevices, getDeviceInterfaces, getInterfaceStats } from '../services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

function MetricsViewer() {
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [interfaces, setInterfaces] = useState([]);
    const [selectedInterface, setSelectedInterface] = useState('');
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(false);
    const [timeRange, setTimeRange] = useState(24);

    useEffect(() => {
        loadDevices();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            loadInterfaces();
        }
    }, [selectedDevice]);

    useEffect(() => {
        if (selectedDevice && selectedInterface) {
            loadStats();
        }
    }, [selectedDevice, selectedInterface, timeRange]);

    const loadDevices = async () => {
        try {
            const data = await getDevices(true); // Only enabled devices
            setDevices(data);
        } catch (error) {
            console.error('Error loading devices:', error);
        }
    };

    const loadInterfaces = async () => {
        try {
            setLoading(true);
            const data = await getDeviceInterfaces(selectedDevice);
            setInterfaces(data);
            if (data.length > 0) {
                setSelectedInterface(data[0].interface_name);
            }
        } catch (error) {
            console.error('Error loading interfaces:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadStats = async () => {
        try {
            setLoading(true);
            const data = await getInterfaceStats(selectedDevice, selectedInterface, timeRange);
            setStats(data);
        } catch (error) {
            console.error('Error loading stats:', error);
        } finally {
            setLoading(false);
        }
    };

    const prepareChartData = () => {
        if (!stats || !stats.metrics) return [];

        // Group metrics by timestamp and OID
        const grouped = {};
        stats.metrics.forEach(metric => {
            const time = new Date(metric.timestamp).toLocaleTimeString();
            if (!grouped[time]) {
                grouped[time] = { time };
            }
            grouped[time][metric.oid_name] = metric.value;
        });

        return Object.values(grouped);
    };

    const getInterfaceStatus = () => {
        if (!stats || !stats.metrics) return null;

        const statusMetric = stats.metrics.find(m => m.oid_name === 'ifOperStatus');
        if (!statusMetric) return null;

        const statusValue = statusMetric.value;
        const statusMap = {
            1: { label: 'Up', class: 'success' },
            2: { label: 'Down', class: 'danger' },
            3: { label: 'Testing', class: 'warning' }
        };

        return statusMap[statusValue] || { label: 'Unknown', class: 'warning' };
    };

    const chartData = prepareChartData();
    const interfaceStatus = getInterfaceStatus();

    return (
        <div className="container">
            <div className="page-header">
                <h1>Metrics Viewer</h1>
                <p>View and analyze SNMP metrics from network devices</p>
            </div>

            {/* Filters */}
            <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Device</label>
                        <select
                            className="select"
                            value={selectedDevice}
                            onChange={(e) => setSelectedDevice(e.target.value)}
                        >
                            <option value="">Select a device...</option>
                            {devices.map(device => (
                                <option key={device.id} value={device.id}>
                                    {device.name} ({device.ip_address})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Interface</label>
                        <select
                            className="select"
                            value={selectedInterface}
                            onChange={(e) => setSelectedInterface(e.target.value)}
                            disabled={!selectedDevice}
                        >
                            <option value="">Select an interface...</option>
                            {interfaces.map((iface, index) => (
                                <option key={index} value={iface.interface_name}>
                                    {iface.interface_name}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Time Range</label>
                        <select
                            className="select"
                            value={timeRange}
                            onChange={(e) => setTimeRange(parseInt(e.target.value))}
                        >
                            <option value="1">Last Hour</option>
                            <option value="6">Last 6 Hours</option>
                            <option value="24">Last 24 Hours</option>
                            <option value="168">Last Week</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Loading State */}
            {loading && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                    <div className="spinner"></div>
                </div>
            )}

            {/* Interface Status */}
            {!loading && stats && interfaceStatus && (
                <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                    <h3>Interface Status</h3>
                    <div style={{ marginTop: 'var(--spacing-lg)', display: 'flex', gap: 'var(--spacing-lg)', alignItems: 'center' }}>
                        <div>
                            <div className="text-sm text-muted">Device</div>
                            <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>{stats.device_name}</div>
                        </div>
                        <div>
                            <div className="text-sm text-muted">Interface</div>
                            <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>{stats.interface_name}</div>
                        </div>
                        <div>
                            <div className="text-sm text-muted">Status</div>
                            <div>
                                <span className={`badge badge-${interfaceStatus.class}`} style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>
                                    {interfaceStatus.label}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Charts */}
            {!loading && stats && chartData.length > 0 && (
                <>
                    {/* Packets Chart */}
                    <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                        <h3>Packet Statistics</h3>
                        <div style={{ marginTop: 'var(--spacing-lg)', height: '300px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
                                    <XAxis dataKey="time" stroke="var(--color-text-muted)" />
                                    <YAxis stroke="var(--color-text-muted)" />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--color-bg-secondary)',
                                            border: '1px solid var(--color-border)',
                                            borderRadius: 'var(--radius-md)'
                                        }}
                                    />
                                    <Legend />
                                    <Line
                                        type="monotone"
                                        dataKey="ifInUcastPkts"
                                        stroke="#10b981"
                                        name="Packets In"
                                        strokeWidth={2}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="ifOutUcastPkts"
                                        stroke="#818cf8"
                                        name="Packets Out"
                                        strokeWidth={2}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Octets Chart */}
                    <div className="glass-card">
                        <h3>Bandwidth Statistics (Octets)</h3>
                        <div style={{ marginTop: 'var(--spacing-lg)', height: '300px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
                                    <XAxis dataKey="time" stroke="var(--color-text-muted)" />
                                    <YAxis stroke="var(--color-text-muted)" />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--color-bg-secondary)',
                                            border: '1px solid var(--color-border)',
                                            borderRadius: 'var(--radius-md)'
                                        }}
                                    />
                                    <Legend />
                                    <Line
                                        type="monotone"
                                        dataKey="ifInOctets"
                                        stroke="#f59e0b"
                                        name="Octets In"
                                        strokeWidth={2}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="ifOutOctets"
                                        stroke="#ef4444"
                                        name="Octets Out"
                                        strokeWidth={2}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </>
            )}

            {/* Empty State */}
            {!loading && !selectedDevice && (
                <div className="glass-card" style={{ textAlign: 'center', padding: '4rem' }}>
                    <h3>No Device Selected</h3>
                    <p className="text-muted">Select a device and interface to view metrics</p>
                </div>
            )}

            {!loading && selectedDevice && (!stats || stats.metrics.length === 0) && (
                <div className="glass-card" style={{ textAlign: 'center', padding: '4rem' }}>
                    <h3>No Metrics Available</h3>
                    <p className="text-muted">No metrics found for the selected device and interface</p>
                </div>
            )}
        </div>
    );
}

export default MetricsViewer;
