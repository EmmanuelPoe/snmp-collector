import React, { useState, useEffect } from 'react';
import { getDevices, getAvailableMetrics, getMetrics } from '../services/api';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    AreaChart, Area
} from 'recharts';

function MetricsViewer() {
    // Selection State
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');

    const [availableMetrics, setAvailableMetrics] = useState({ modules: {} });
    const [selectedModule, setSelectedModule] = useState('');

    // Metrics Selection (multi-select)
    const [selectedMetricNames, setSelectedMetricNames] = useState([]);
    const [selectedInterface, setSelectedInterface] = useState(''); // Use for filtering valid metrics if needed

    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [timeRange, setTimeRange] = useState(24);

    useEffect(() => {
        loadDevices();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            loadAvailableMetrics();
            setSelectedModule('');
            setSelectedMetricNames([]);
            setSelectedInterface('');
            setChartData([]);
        }
    }, [selectedDevice]);

    useEffect(() => {
        if (selectedModule) {
            // Select default metrics for if_mib
            if (selectedModule === 'if_mib') {
                setSelectedMetricNames(['ifInOctets', 'ifOutOctets']);
            } else {
                setSelectedMetricNames([]);
            }
        }
    }, [selectedModule]);

    useEffect(() => {
        if (selectedDevice && selectedModule && selectedMetricNames.length > 0) {
            loadChartData();
        }
    }, [selectedDevice, selectedModule, selectedMetricNames, selectedInterface, timeRange]);


    const loadDevices = async () => {
        try {
            const data = await getDevices(true);
            setDevices(data);
        } catch (error) {
            console.error('Error loading devices:', error);
        }
    };

    const loadAvailableMetrics = async () => {
        try {
            const data = await getAvailableMetrics(selectedDevice);
            setAvailableMetrics(data);

            // Auto-select first module if available
            const modules = Object.keys(data.modules);
            if (modules.length > 0) {
                // Prefer if_mib if available
                if (modules.includes('if_mib')) {
                    setSelectedModule('if_mib');
                } else {
                    setSelectedModule(modules[0]);
                }
            }
        } catch (error) {
            console.error('Error loading available metrics:', error);
        }
    };

    const loadChartData = async () => {
        setLoading(true);
        try {
            // Calculate start/end time
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - timeRange * 60 * 60 * 1000);

            // Fetch metrics
            // Note: We might need multiple calls if interface filtering is strict, 
            // but for now we fetch by module/device and filter locally or trust backend
            const params = {
                device_id: selectedDevice,
                module: selectedModule,
                start_time: startTime.toISOString(),
                end_time: endTime.toISOString(),
                limit: 2000 // Increase limit for multi-metric
            };

            if (selectedInterface) {
                params.interface_name = selectedInterface;
            }

            const data = await getMetrics(params);
            processChartData(data);
        } catch (error) {
            console.error('Error loading chart data:', error);
        } finally {
            setLoading(false);
        }
    };

    const processChartData = (rawMetrics) => {
        // We need to group by Timestamp -> Interface (if multiple) -> MetricName
        // But for visual simplicity, let's assume we view ONE interface at a time for if_mib
        // OR we aggregate.

        if (!selectedInterface && selectedModule === 'if_mib') {
            // Warn user to select interface
            // or maybe we map: timestamp -> metric_name (sum?)
            // let's stick to simple timestamp grouping for now
        }

        const grouped = {};

        rawMetrics.forEach(m => {
            // Filter by selected metrics just in case
            if (!selectedMetricNames.includes(m.oid_name)) return;

            // Round timestamp to minute for alignment
            const date = new Date(m.timestamp);
            date.setSeconds(0, 0);
            const timeKey = date.getTime();

            if (!grouped[timeKey]) {
                grouped[timeKey] = {
                    timestamp: timeKey,
                    timeLabel: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                };
            }

            // If viewing multiple interfaces, this might look weird (overlapping values)
            // Ideally we filter by interface_name
            grouped[timeKey][m.oid_name] = m.value;
        });

        // Convert to array and sort
        const chartArray = Object.values(grouped).sort((a, b) => a.timestamp - b.timestamp);
        setChartData(chartArray);
    };

    const handleMetricToggle = (metricName) => {
        setSelectedMetricNames(prev => {
            if (prev.includes(metricName)) {
                return prev.filter(m => m !== metricName);
            } else {
                return [...prev, metricName];
            }
        });
    };

    // Helper for formatting bytes
    const formatValue = (val, type) => {
        if (val === undefined || val === null) return 'N/A';
        if (type === 'bytes') {
            if (val === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(val) / Math.log(k));
            return parseFloat((val / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        if (type === 'status') {
            const mapping = { 1: 'Up', 2: 'Down', 3: 'Testing', 4: 'Unknown', 5: 'Dormant', 6: 'Not Present', 7: 'Lower Layer Down' };
            return mapping[val] || val;
        }
        return val.toLocaleString();
    };

    // Helper to render specific chart types
    const renderCharts = () => {
        if (!selectedModule || chartData.length === 0) return null;

        if (selectedModule === 'if_mib') {
            const groups = [
                {
                    title: 'Network Traffic',
                    metrics: ['ifInOctets', 'ifOutOctets', 'ifHCInOctets', 'ifHCOutOctets'],
                    type: 'area',
                    unit: 'bytes'
                },
                {
                    title: 'Packet Throughput',
                    metrics: ['ifInUcastPkts', 'ifOutUcastPkts', 'ifInMulticastPkts', 'ifOutMulticastPkts', 'ifInBroadcastPkts', 'ifOutBroadcastPkts'],
                    type: 'line',
                    unit: 'packets'
                },
                {
                    title: 'Errors & Integrity',
                    metrics: ['ifInErrors', 'ifOutErrors', 'ifInUnknownProtos'],
                    type: 'line',
                    unit: 'count'
                },
                {
                    title: 'Buffer Discards',
                    metrics: ['ifInDiscards', 'ifOutDiscards'],
                    type: 'bar',
                    unit: 'count'
                },
                {
                    title: 'Link Status',
                    metrics: ['ifOperStatus', 'ifAdminStatus'],
                    type: 'step',
                    unit: 'status'
                }
            ];

            const colors = ['#10b981', '#3b82f6', '#ef4444', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

            return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
                    {groups.map((group, groupIdx) => {
                        const activeMetrics = selectedMetricNames.filter(m => group.metrics.includes(m));
                        if (activeMetrics.length === 0) return null;

                        return (
                            <div key={group.title} className="glass-card">
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                    <h3>{group.title}</h3>
                                    <span className="text-muted" style={{ fontSize: '0.8rem' }}>{group.unit}</span>
                                </div>
                                <div style={{ height: '300px' }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        {group.type === 'area' ? (
                                            <AreaChart data={chartData}>
                                                <defs>
                                                    {activeMetrics.map((m, i) => (
                                                        <linearGradient key={`grad-${m}`} id={`color-${m}`} x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor={colors[i % colors.length]} stopOpacity={0.3} />
                                                            <stop offset="95%" stopColor={colors[i % colors.length]} stopOpacity={0} />
                                                        </linearGradient>
                                                    ))}
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                                <XAxis dataKey="timeLabel" stroke="#64748b" fontSize={11} />
                                                <YAxis stroke="#64748b" fontSize={11} tickFormatter={(val) => formatValue(val, group.unit)} />
                                                <Tooltip
                                                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                                    formatter={(val) => [formatValue(val, group.unit), '']}
                                                />
                                                <Legend iconType="circle" />
                                                {activeMetrics.map((m, i) => (
                                                    <Area key={m} type="monotone" dataKey={m} stroke={colors[i % colors.length]} fillOpacity={1} fill={`url(#color-${m})`} name={m.replace('if', '')} />
                                                ))}
                                            </AreaChart>
                                        ) : (
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                                <XAxis dataKey="timeLabel" stroke="#64748b" fontSize={11} />
                                                <YAxis stroke="#64748b" fontSize={11} tickFormatter={(val) => formatValue(val, group.unit)} />
                                                <Tooltip
                                                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                                    formatter={(val) => [formatValue(val, group.unit), '']}
                                                />
                                                <Legend iconType="circle" />
                                                {activeMetrics.map((m, i) => (
                                                    <Line key={m} type={group.type === 'step' ? 'stepAfter' : 'monotone'} dataKey={m} stroke={colors[i % colors.length]} dot={false} name={m.replace('if', '')} strokeWidth={2} />
                                                ))}
                                            </LineChart>
                                        )}
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        );
                    })}

                    {/* Generic Fallback for other modules or miscellaneous if_mib metrics */}
                    {selectedMetricNames.filter(m => !groups.some(g => g.metrics.includes(m))).length > 0 && (
                        <div className="glass-card">
                            <h3>Extended Metrics</h3>
                            <div style={{ height: '300px', marginTop: '1rem' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                        <XAxis dataKey="timeLabel" stroke="#64748b" fontSize={11} />
                                        <YAxis stroke="#64748b" fontSize={11} />
                                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                                        <Legend iconType="circle" />
                                        {selectedMetricNames.filter(m => !groups.some(g => g.metrics.includes(m))).map((metric, idx) => (
                                            <Line key={metric} type="monotone" dataKey={metric} stroke={`hsl(${idx * 45 + 200}, 70%, 60%)`} dot={false} name={metric} />
                                        ))}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        return <div>Select metrics to view data.</div>;
    };


    return (
        <div className="container">
            <div className="page-header">
                <h1>Metrics Explorer</h1>
                <p>Multi-module visualization and analysis</p>
            </div>

            {/* Selection Panel */}
            <div className="glass-card" style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>

                    {/* 1. Device */}
                    <div className="form-group">
                        <label className="form-label">Device</label>
                        <select className="select" value={selectedDevice} onChange={e => setSelectedDevice(e.target.value)}>
                            <option value="">Select Device...</option>
                            {devices.map(d => (
                                <option key={d.id} value={d.id}>{d.name}</option>
                            ))}
                        </select>
                    </div>

                    {/* 2. Module */}
                    <div className="form-group">
                        <label className="form-label">Module</label>
                        <select
                            className="select"
                            value={selectedModule}
                            onChange={e => setSelectedModule(e.target.value)}
                            disabled={!selectedDevice}
                        >
                            <option value="">Select Module...</option>
                            {availableMetrics && availableMetrics.modules && Object.keys(availableMetrics.modules).map(m => (
                                <option key={m} value={m}>{m}</option>
                            ))}
                        </select>
                    </div>

                    {/* 3. Interface (Optional but recommended for if_mib) */}
                    {selectedModule && availableMetrics.modules[selectedModule]?.interfaces?.length > 0 && (
                        <div className="form-group">
                            <label className="form-label">Interface</label>
                            <select
                                className="select"
                                value={selectedInterface}
                                onChange={e => setSelectedInterface(e.target.value)}
                            >
                                <option value="">All Interfaces</option>
                                {availableMetrics.modules[selectedModule].interfaces.map(iface => (
                                    <option key={iface} value={iface}>{iface}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    {/* Time Range */}
                    <div className="form-group">
                        <label className="form-label">Time Range</label>
                        <select className="select" value={timeRange} onChange={e => setTimeRange(e.target.value)}>
                            <option value="1">Last Hour</option>
                            <option value="24">Last 24 Hours</option>
                            <option value="168">Last 7 Days</option>
                        </select>
                    </div>

                </div>

                {/* 4. Metrics Checkboxes */}
                {selectedModule && availableMetrics.modules[selectedModule] && (
                    <div style={{ marginTop: '1.5rem', borderTop: '1px solid #374151', paddingTop: '1rem' }}>
                        <label className="form-label" style={{ marginBottom: '0.5rem', display: 'block' }}>Select Metrics:</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                            {availableMetrics.modules[selectedModule].metrics.map(metric => (
                                <label key={metric}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                                        background: selectedMetricNames.includes(metric) ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255,255,255,0.05)',
                                        padding: '0.25rem 0.75rem', borderRadius: '20px', cursor: 'pointer',
                                        border: selectedMetricNames.includes(metric) ? '1px solid #3b82f6' : '1px solid transparent'
                                    }}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedMetricNames.includes(metric)}
                                        onChange={() => handleMetricToggle(metric)}
                                        style={{ accentColor: '#3b82f6' }}
                                    />
                                    <span style={{ fontSize: '0.9rem' }}>{metric}</span>
                                </label>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Visualization Area */}
            {loading ? (
                <div style={{ textAlign: 'center', padding: '3rem' }}>Loading data...</div>
            ) : (
                <div style={{ animation: 'fadeIn 0.5s' }}>
                    {renderCharts()}
                </div>
            )}

            {!selectedDevice && (
                <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>
                    Select a device to begin exploration.
                </div>
            )}
        </div>
    );
}

export default MetricsViewer;
