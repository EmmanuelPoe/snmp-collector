import React, { useState, useEffect } from 'react';
import {
    getDevices,
    getSchedules,
    updateSchedule,
    createSchedule,
    reloadConfig,
    getModules,
    getModuleConfig,
    updateModuleConfig
} from '../services/api';

function ConfigurationManager() {
    const [modules, setModules] = useState([]);
    const [devices, setDevices] = useState([]);
    const [schedules, setSchedules] = useState([]);
    const [loading, setLoading] = useState(true);

    // Modal State
    const [showModal, setShowModal] = useState(false);
    const [newSchedule, setNewSchedule] = useState({ device_id: '', interval_seconds: 60, enabled: true });

    // Module Editor State
    const [selectedModule, setSelectedModule] = useState('');
    const [yamlContent, setYamlContent] = useState('');
    const [originalYaml, setOriginalYaml] = useState('');
    const [editorStatus, setEditorStatus] = useState(''); // '', 'loading', 'saving', 'success', 'error'
    const [editorMessage, setEditorMessage] = useState('');

    useEffect(() => {
        loadInitialData();
    }, []);

    useEffect(() => {
        if (selectedModule) {
            loadModuleConfig(selectedModule);
        } else {
            setYamlContent('');
            setOriginalYaml('');
        }
    }, [selectedModule]);

    const loadInitialData = async () => {
        setLoading(true);
        try {
            const [modulesData, devicesData, schedulesData] = await Promise.all([
                getModules(),
                getDevices(),
                getSchedules()
            ]);
            setModules(modulesData);
            setDevices(devicesData);
            setSchedules(schedulesData);

            if (modulesData.length > 0) {
                setSelectedModule(modulesData[0]);
            }
        } catch (error) {
            console.error('Error loading initial data:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadModuleConfig = async (moduleName) => {
        setEditorStatus('loading');
        try {
            const data = await getModuleConfig(moduleName);
            setYamlContent(data.yaml);
            setOriginalYaml(data.yaml);
            setEditorStatus('');
        } catch (error) {
            console.error('Error loading module config:', error);
            setEditorStatus('error');
            setEditorMessage('Failed to load module configuration');
        }
    };

    const handleSaveModule = async () => {
        setEditorStatus('saving');
        setEditorMessage('');
        try {
            await updateModuleConfig(selectedModule, yamlContent);
            setOriginalYaml(yamlContent);
            setEditorStatus('success');
            setEditorMessage('Configuration saved and reloaded successfully');
            setTimeout(() => setEditorStatus(''), 3000);
        } catch (error) {
            console.error('Error saving module:', error);
            setEditorStatus('error');
            setEditorMessage('Error: ' + (error.response?.data?.detail || error.message));
        }
    };

    const handleToggleSchedule = async (deviceId, currentSchedule) => {
        try {
            const updated = await updateSchedule(deviceId, { enabled: !currentSchedule.enabled });
            setSchedules(prev => prev.map(s => s.device_id === deviceId ? updated : s));
        } catch (error) {
            console.error('Error toggling schedule:', error);
            alert('Failed to update schedule');
        }
    };

    const handleIntervalChange = async (deviceId, interval) => {
        try {
            const updated = await updateSchedule(deviceId, { interval_seconds: parseInt(interval) });
            setSchedules(prev => prev.map(s => s.device_id === deviceId ? updated : s));
        } catch (error) {
            console.error('Error updating interval:', error);
        }
    };

    const handleCreateSchedule = async (e) => {
        e.preventDefault();
        try {
            const created = await createSchedule(newSchedule);
            setSchedules(prev => [...prev, created]);
            setShowModal(false);
            setNewSchedule({ device_id: '', interval_seconds: 60, enabled: true });
        } catch (error) {
            console.error('Error creating schedule:', error);
            alert('Error: ' + (error.response?.data?.detail || 'Failed to create schedule'));
        }
    };

    const handleReloadConfig = async () => {
        try {
            await reloadConfig();
            alert('Exporter reloaded successfully');
        } catch (error) {
            console.error('Error reloading:', error);
            alert('Reload failed');
        }
    };

    // Helper to find schedule for a device
    const getDeviceSchedule = (deviceId) => schedules.find(s => s.device_id === deviceId);

    // Devices without schedules
    const availableDevices = devices.filter(d => !getDeviceSchedule(d.id));

    if (loading) return <div className="container" style={{ textAlign: 'center', padding: '5rem' }}>Loading Configuration...</div>;

    return (
        <div className="container" style={{ animation: 'fadeIn 0.5s' }}>
            <div className="page-header">
                <h1>Configuration Manager</h1>
                <p>Fine-tune SNMP collection parameters and backend modules</p>
            </div>

            {/* 1. Collection Schedules Table */}
            <div className="glass-card" style={{ marginBottom: '2.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                    <div>
                        <h3>Device Collection Schedules</h3>
                        <p className="text-muted">Manage polling intervals and status for each device.</p>
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={() => setShowModal(true)}
                        disabled={availableDevices.length === 0}
                    >
                        + Add Device Schedule
                    </button>
                </div>

                <div style={{ overflowX: 'auto' }}>
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Device Name</th>
                                <th>IP Address</th>
                                <th>Interval</th>
                                <th>Status</th>
                                <th>Last Collection</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {devices.map(device => {
                                const sched = getDeviceSchedule(device.id);
                                return (
                                    <tr key={device.id}>
                                        <td style={{ fontWeight: '500' }}>{device.name}</td>
                                        <td className="text-muted">{device.ip_address}</td>
                                        <td>
                                            {sched ? (
                                                <select
                                                    className="select"
                                                    style={{ padding: '0.2rem 0.5rem', width: 'auto' }}
                                                    value={sched.interval_seconds}
                                                    onChange={(e) => handleIntervalChange(device.id, e.target.value)}
                                                >
                                                    <option value="30">30s</option>
                                                    <option value="60">1m</option>
                                                    <option value="300">5m</option>
                                                    <option value="900">15m</option>
                                                    <option value="3600">1h</option>
                                                </select>
                                            ) : (
                                                <span className="text-muted" style={{ fontStyle: 'italic', fontSize: '0.85rem' }}>Not scheduled</span>
                                            )}
                                        </td>
                                        <td>
                                            {sched ? (
                                                <span className={`badge ${sched.enabled ? 'badge-success' : 'badge-danger'}`}>
                                                    {sched.enabled ? 'Active' : 'Paused'}
                                                </span>
                                            ) : (
                                                <span className="badge" style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#64748b' }}>None</span>
                                            )}
                                        </td>
                                        <td className="text-muted" style={{ fontSize: '0.85rem' }}>
                                            {sched?.last_collection ? new Date(sched.last_collection).toLocaleString() : 'Never'}
                                        </td>
                                        <td>
                                            {sched ? (
                                                <button
                                                    className={`btn ${sched.enabled ? 'btn-secondary' : 'btn-primary'}`}
                                                    style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem', minWidth: '80px' }}
                                                    onClick={() => handleToggleSchedule(device.id, sched)}
                                                >
                                                    {sched.enabled ? 'Pause' : 'Resume'}
                                                </button>
                                            ) : (
                                                <button
                                                    className="btn btn-primary"
                                                    style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem', minWidth: '80px' }}
                                                    onClick={() => {
                                                        setNewSchedule({ ...newSchedule, device_id: device.id });
                                                        setShowModal(true);
                                                    }}
                                                >
                                                    Add
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Modal for Adding Schedule */}
            {showModal && (
                <div className="modal-overlay" style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.8)', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', zIndex: 1000,
                    backdropFilter: 'blur(4px)'
                }}>
                    <div className="glass-card" style={{ width: '400px', maxWidth: '90%' }}>
                        <h3 style={{ marginBottom: '1.5rem' }}>Configure Collection Schedule</h3>
                        <form onSubmit={handleCreateSchedule}>
                            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                                <label className="form-label">Device</label>
                                <select
                                    className="select"
                                    required
                                    value={newSchedule.device_id}
                                    onChange={(e) => setNewSchedule({ ...newSchedule, device_id: e.target.value })}
                                >
                                    <option value="">Select a device...</option>
                                    {availableDevices.map(d => (
                                        <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>
                                    ))}
                                    {/* Include already selected device if we came from 'Add' button */}
                                    {newSchedule.device_id && !availableDevices.find(d => d.id === parseInt(newSchedule.device_id)) && (
                                        <option value={newSchedule.device_id}>
                                            {devices.find(d => d.id === parseInt(newSchedule.device_id))?.name}
                                        </option>
                                    )}
                                </select>
                            </div>

                            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                                <label className="form-label">Polling Interval</label>
                                <select
                                    className="select"
                                    value={newSchedule.interval_seconds}
                                    onChange={(e) => setNewSchedule({ ...newSchedule, interval_seconds: parseInt(e.target.value) })}
                                >
                                    <option value="30">30 Seconds</option>
                                    <option value="60">1 Minute</option>
                                    <option value="300">5 Minutes</option>
                                    <option value="900">15 Minutes</option>
                                    <option value="3600">1 Hour</option>
                                </select>
                            </div>

                            <div className="form-group" style={{ marginBottom: '2rem' }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
                                    <input
                                        type="checkbox"
                                        checked={newSchedule.enabled}
                                        onChange={(e) => setNewSchedule({ ...newSchedule, enabled: e.target.checked })}
                                        style={{ width: '18px', height: '18px' }}
                                    />
                                    <span style={{ fontSize: '0.95rem' }}>Enable Collection Immediately</span>
                                </label>
                            </div>

                            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary" disabled={!newSchedule.device_id}>Create Schedule</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* 2. Module Editor Section */}
            <div className="glass-card" style={{ marginBottom: '2.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                    <div>
                        <h3>Module Definitions</h3>
                        <p className="text-muted">Directly modify YAML configuration for SNMP modules.</p>
                    </div>
                    <div style={{ width: '220px' }}>
                        <select
                            className="select"
                            value={selectedModule}
                            onChange={(e) => setSelectedModule(e.target.value)}
                        >
                            {modules.map(mod => (
                                <option key={mod} value={mod}>{mod}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <textarea
                    className="code-editor"
                    value={yamlContent}
                    onChange={(e) => setYamlContent(e.target.value)}
                    spellCheck="false"
                    style={{
                        width: '100%', minHeight: '350px',
                        fontFamily: "'Fira Code', 'Courier New', monospace",
                        padding: '1.25rem', backgroundColor: '#0f172a', color: '#e2e8f0',
                        border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px',
                        lineHeight: '1.5', fontSize: '13px'
                    }}
                />

                <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        {editorMessage && (
                            <span style={{ color: editorStatus === 'error' ? '#ef4444' : '#10b981', fontSize: '0.9rem' }}>
                                {editorMessage}
                            </span>
                        )}
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button
                            className="btn btn-secondary"
                            onClick={() => setYamlContent(originalYaml)}
                            disabled={yamlContent === originalYaml || editorStatus === 'saving'}
                        >
                            Reset
                        </button>
                        <button
                            className="btn btn-primary"
                            onClick={handleSaveModule}
                            disabled={yamlContent === originalYaml || editorStatus === 'saving'}
                        >
                            {editorStatus === 'saving' ? 'Applying...' : 'Apply Changes'}
                        </button>
                    </div>
                </div>
            </div>

            {/* 3. Global Actions */}
            <div className="glass-card" style={{ background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                <h3 style={{ color: '#f59e0b' }}>System Maintenance</h3>
                <p className="text-muted">Use these tools only when manual intervention is required.</p>
                <div style={{ marginTop: '1.25rem' }}>
                    <button className="btn btn-warning" onClick={handleReloadConfig}>
                        Reload SNMP Exporter Service
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ConfigurationManager;
