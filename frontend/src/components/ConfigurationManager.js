import React, { useState, useEffect } from 'react';
import {
    getOIDs,
    createOID,
    deleteOID,
    getDevices,
    getSchedule,
    updateSchedule,
    reloadConfig
} from '../services/api';

function ConfigurationManager() {
    const [oids, setOids] = useState([]);
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [schedule, setSchedule] = useState(null);
    const [showOidModal, setShowOidModal] = useState(false);
    const [oidForm, setOidForm] = useState({
        oid: '',
        oid_name: '',
        description: '',
        enabled: true
    });

    useEffect(() => {
        loadOIDs();
        loadDevices();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            loadSchedule();
        }
    }, [selectedDevice]);

    const loadOIDs = async () => {
        try {
            const data = await getOIDs();
            setOids(data);
        } catch (error) {
            console.error('Error loading OIDs:', error);
        }
    };

    const loadDevices = async () => {
        try {
            const data = await getDevices();
            setDevices(data);
            if (data.length > 0) {
                setSelectedDevice(data[0].id);
            }
        } catch (error) {
            console.error('Error loading devices:', error);
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

    const handleAddOID = async (e) => {
        e.preventDefault();
        try {
            await createOID(oidForm);
            setShowOidModal(false);
            setOidForm({ oid: '', oid_name: '', description: '', enabled: true });
            loadOIDs();
        } catch (error) {
            console.error('Error adding OID:', error);
            alert('Error adding OID: ' + (error.response?.data?.detail || error.message));
        }
    };

    const handleDeleteOID = async (oidId) => {
        if (window.confirm('Are you sure you want to delete this OID?')) {
            try {
                await deleteOID(oidId);
                loadOIDs();
            } catch (error) {
                console.error('Error deleting OID:', error);
            }
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
                <p>Manage SNMP OIDs and collection schedules</p>
            </div>

            {/* SNMP OIDs Section */}
            <div className="glass-card" style={{ marginBottom: 'var(--spacing-2xl)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-lg)' }}>
                    <h3>SNMP OIDs</h3>
                    <button className="btn btn-primary" onClick={() => setShowOidModal(true)}>
                        + Add OID
                    </button>
                </div>

                <table className="data-table">
                    <thead>
                        <tr>
                            <th>OID</th>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {oids.length === 0 ? (
                            <tr>
                                <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-muted)' }}>
                                    No OIDs configured
                                </td>
                            </tr>
                        ) : (
                            oids.map(oid => (
                                <tr key={oid.id}>
                                    <td><code style={{ fontSize: '0.875rem' }}>{oid.oid}</code></td>
                                    <td><strong>{oid.oid_name}</strong></td>
                                    <td className="text-sm text-muted">{oid.description || 'N/A'}</td>
                                    <td>
                                        <span className={`badge badge-${oid.enabled ? 'success' : 'danger'}`}>
                                            {oid.enabled ? 'Enabled' : 'Disabled'}
                                        </span>
                                    </td>
                                    <td>
                                        <button
                                            className="btn btn-danger"
                                            style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                                            onClick={() => handleDeleteOID(oid.id)}
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
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
                    Reload the SNMP Exporter configuration to apply changes
                </p>
                <button
                    className="btn btn-warning"
                    style={{ marginTop: 'var(--spacing-lg)' }}
                    onClick={handleReloadConfig}
                >
                    Reload SNMP Exporter
                </button>
            </div>

            {/* Add OID Modal */}
            {showOidModal && (
                <div className="modal-overlay" onClick={() => setShowOidModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>Add SNMP OID</h3>
                            <button className="modal-close" onClick={() => setShowOidModal(false)}>×</button>
                        </div>

                        <form onSubmit={handleAddOID}>
                            <div className="form-group">
                                <label className="form-label">OID *</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={oidForm.oid}
                                    onChange={(e) => setOidForm({ ...oidForm, oid: e.target.value })}
                                    required
                                    placeholder="e.g., 1.3.6.1.2.1.2.2.1.10"
                                />
                            </div>

                            <div className="form-group">
                                <label className="form-label">OID Name *</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={oidForm.oid_name}
                                    onChange={(e) => setOidForm({ ...oidForm, oid_name: e.target.value })}
                                    required
                                    placeholder="e.g., ifInOctets"
                                />
                            </div>

                            <div className="form-group">
                                <label className="form-label">Description</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={oidForm.description}
                                    onChange={(e) => setOidForm({ ...oidForm, description: e.target.value })}
                                    placeholder="Optional description"
                                />
                            </div>

                            <div className="form-group">
                                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <input
                                        type="checkbox"
                                        checked={oidForm.enabled}
                                        onChange={(e) => setOidForm({ ...oidForm, enabled: e.target.checked })}
                                    />
                                    <span className="form-label" style={{ margin: 0 }}>Enabled</span>
                                </label>
                            </div>

                            <div className="action-buttons">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowOidModal(false)}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary">
                                    Add OID
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ConfigurationManager;
