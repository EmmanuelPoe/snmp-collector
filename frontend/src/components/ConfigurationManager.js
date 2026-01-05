import React, { useState, useEffect } from 'react';
import {
    getDevices,
    getSchedule,
    updateSchedule,
    reloadConfig,
    getModules,
    getModuleConfig,
    updateModuleConfig
} from '../services/api';

function ConfigurationManager() {
    const [modules, setModules] = useState([]);
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [schedule, setSchedule] = useState(null);

    // Module Editor State
    const [selectedModule, setSelectedModule] = useState('');
    const [yamlContent, setYamlContent] = useState('');
    const [originalYaml, setOriginalYaml] = useState('');
    const [editorStatus, setEditorStatus] = useState(''); // '', 'loading', 'saving', 'success', 'error'
    const [editorMessage, setEditorMessage] = useState('');

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            loadSchedule();
        }
    }, [selectedDevice]);

    useEffect(() => {
        if (selectedModule) {
            loadModuleConfig(selectedModule);
        } else {
            setYamlContent('');
            setOriginalYaml('');
        }
    }, [selectedModule]);

    const loadData = async () => {
        try {
            const [modulesData, devicesData] = await Promise.all([
                getModules(),
                getDevices()
            ]);
            setModules(modulesData);
            setDevices(devicesData);
            if (devicesData.length > 0) {
                setSelectedDevice(devicesData[0].id);
            }
            if (modulesData.length > 0) {
                setSelectedModule(modulesData[0]);
            }
        } catch (error) {
            console.error('Error loading config data:', error);
        }
    };

    const loadSchedule = async () => {
        try {
            const data = await getSchedule(selectedDevice);
            setSchedule(data);
        } catch (error) {
            console.error('Error loading schedule:', error);
            setSchedule(null);
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

            // Clear success message after 3 seconds
            setTimeout(() => {
                if (editorStatus === 'success') {
                    setEditorStatus('');
                    setEditorMessage('');
                }
            }, 3000);
        } catch (error) {
            console.error('Error saving module:', error);
            setEditorStatus('error');
            setEditorMessage('Error saving configuration: ' + (error.response?.data?.detail || error.message));
        }
    };

    const handleResetModule = () => {
        if (window.confirm('Reset changes to last saved version?')) {
            setYamlContent(originalYaml);
            setEditorStatus('');
            setEditorMessage('');
        }
    };

    const handleUpdateSchedule = async () => {
        if (!schedule) return;
        try {
            await updateSchedule(selectedDevice, {
                interval_seconds: schedule.interval_seconds,
                enabled: schedule.enabled
            });
            alert('Schedule updated successfully');
        } catch (error) {
            console.error('Error updating schedule:', error);
            alert('Error updating schedule');
        }
    };

    const handleReloadConfig = async () => {
        try {
            await reloadConfig();
            alert('Configuration reloaded successfully');
        } catch (error) {
            console.error('Error reloading config:', error);
            alert('Error reloading configuration');
        }
    };

    return (
        <div className="container">
            <div className="page-header">
                <h1>Configuration Manager</h1>
                <p>Manage SNMP Modules and collection schedules</p>
            </div>

            {/* Module Editor Section */}
            <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-lg)' }}>
                    <div>
                        <h3>Module Editor</h3>
                        <p className="text-muted">Select a module to view or edit its YAML configuration.</p>
                    </div>
                    <div style={{ width: '200px' }}>
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

                {editorStatus === 'loading' ? (
                    <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>
                ) : (
                    <div className="editor-container">
                        <textarea
                            className="code-editor"
                            value={yamlContent}
                            onChange={(e) => setYamlContent(e.target.value)}
                            spellCheck="false"
                            style={{
                                width: '100%',
                                minHeight: '400px',
                                fontFamily: 'monospace',
                                padding: '1rem',
                                backgroundColor: '#1e1e1e',
                                color: '#d4d4d4',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)',
                                resize: 'vertical'
                            }}
                        />

                        <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div className={`status-message ${editorStatus}`}>
                                {editorMessage && (
                                    <span style={{
                                        color: editorStatus === 'error' ? 'var(--color-danger)' : 'var(--color-success)',
                                        fontWeight: 'bold'
                                    }}>
                                        {editorMessage}
                                    </span>
                                )}
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button
                                    className="btn btn-secondary"
                                    onClick={handleResetModule}
                                    disabled={editorStatus === 'saving' || yamlContent === originalYaml}
                                >
                                    Reset
                                </button>
                                <button
                                    className="btn btn-primary"
                                    onClick={handleSaveModule}
                                    disabled={editorStatus === 'saving' || yamlContent === originalYaml}
                                >
                                    {editorStatus === 'saving' ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Collection Schedule Section */}
            <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                <h3>Collection Schedule</h3>

                <div className="form-group" style={{ marginTop: 'var(--spacing-lg)' }}>
                    <label className="form-label">Device</label>
                    <select
                        className="select"
                        value={selectedDevice}
                        onChange={(e) => setSelectedDevice(e.target.value)}
                    >
                        {devices.map(device => (
                            <option key={device.id} value={device.id}>
                                {device.name} ({device.ip_address})
                            </option>
                        ))}
                    </select>
                </div>

                {schedule && (
                    <>
                        <div className="form-row" style={{ marginTop: 'var(--spacing-lg)' }}>
                            <div className="form-group">
                                <label className="form-label">Collection Interval (seconds)</label>
                                <input
                                    className="input"
                                    type="number"
                                    value={schedule.interval_seconds}
                                    onChange={(e) => setSchedule({ ...schedule, interval_seconds: parseInt(e.target.value) })}
                                    min="10"
                                    max="86400"
                                />
                            </div>

                            <div className="form-group">
                                <label className="form-label">Last Collection</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={schedule.last_collection ? new Date(schedule.last_collection).toLocaleString() : 'Never'}
                                    disabled
                                />
                            </div>
                        </div>

                        <div className="form-group" style={{ marginTop: 'var(--spacing-lg)' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <input
                                    type="checkbox"
                                    checked={schedule.enabled}
                                    onChange={(e) => setSchedule({ ...schedule, enabled: e.target.checked })}
                                />
                                <span className="form-label" style={{ margin: 0 }}>Schedule Enabled</span>
                            </label>
                        </div>

                        <button
                            className="btn btn-primary"
                            style={{ marginTop: 'var(--spacing-lg)' }}
                            onClick={handleUpdateSchedule}
                        >
                            Update Schedule
                        </button>
                    </>
                )}

                {!schedule && selectedDevice && (
                    <div style={{ marginTop: 'var(--spacing-lg)', color: 'var(--color-text-muted)' }}>
                        No schedule found for this device
                    </div>
                )}
            </div>

            {/* Reload Configuration */}
            <div className="glass-card">
                <h3>Reload Configuration</h3>
                <p className="text-muted" style={{ marginTop: 'var(--spacing-md)' }}>
                    Reload the SNMP Exporter configuration manually if needed.
                </p>
                <button
                    className="btn btn-warning"
                    style={{ marginTop: 'var(--spacing-lg)' }}
                    onClick={handleReloadConfig}
                >
                    Reload SNMP Exporter
                </button>
            </div>
        </div>
    );
}

export default ConfigurationManager;
