import React, { useState, useEffect } from 'react';
import { getDevices, createDevice, updateDevice, deleteDevice, triggerCollection, getModules } from '../services/api';

function DeviceManagement() {
    const [devices, setDevices] = useState([]);
    const [availableModules, setAvailableModules] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingDevice, setEditingDevice] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        ip_address: '',
        snmp_version: '2c',
        snmp_community: 'public',
        snmp_port: 161,
        snmp_modules: ['if_mib'],
        device_type: 'switch',
        description: '',
        enabled: true
    });

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [devicesData, modulesData] = await Promise.all([
                getDevices(),
                getModules()
            ]);
            setDevices(devicesData);
            setAvailableModules(modulesData);
        } catch (error) {
            console.error('Error loading data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (editingDevice) {
                await updateDevice(editingDevice.id, formData);
            } else {
                await createDevice(formData);
            }
            setShowModal(false);
            resetForm();
            loadData();
        } catch (error) {
            console.error('Error saving device:', error);
            alert('Error saving device: ' + (error.response?.data?.detail || error.message));
        }
    };

    const handleEdit = (device) => {
        setEditingDevice(device);
        setFormData({
            name: device.name,
            ip_address: device.ip_address,
            snmp_version: device.snmp_version,
            snmp_community: device.snmp_community,
            snmp_port: device.snmp_port,
            snmp_modules: device.snmp_modules || ['if_mib'],
            device_type: device.device_type || 'switch',
            description: device.description || '',
            enabled: device.enabled
        });
        setShowModal(true);
    };

    const handleDelete = async (deviceId) => {
        if (window.confirm('Are you sure you want to delete this device?')) {
            try {
                await deleteDevice(deviceId);
                loadData(); // Reload both to be safe
            } catch (error) {
                console.error('Error deleting device:', error);
                alert('Error deleting device');
            }
        }
    };

    const handleCollect = async (deviceId) => {
        try {
            await triggerCollection(deviceId);
            alert('Collection triggered successfully');
        } catch (error) {
            console.error('Error triggering collection:', error);
            alert('Error triggering collection');
        }
    };

    const handleModuleChange = (e) => {
        const selectedOptions = Array.from(e.target.selectedOptions, option => option.value);
        setFormData({ ...formData, snmp_modules: selectedOptions });
    };

    const resetForm = () => {
        setEditingDevice(null);
        setFormData({
            name: '',
            ip_address: '',
            snmp_version: '2c',
            snmp_community: 'public',
            snmp_port: 161,
            snmp_modules: ['if_mib'],
            device_type: 'switch',
            description: '',
            enabled: true
        });
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h1>Device Management</h1>
                        <p>Manage network devices for SNMP collection</p>
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={() => { resetForm(); setShowModal(true); }}
                    >
                        + Add Device
                    </button>
                </div>
            </div>

            {/* Devices Table */}
            <div className="glass-card">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>IP Address</th>
                            <th>Type</th>
                            <th>SNMP Version</th>
                            <th>Modules</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {devices.length === 0 ? (
                            <tr>
                                <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-muted)' }}>
                                    No devices found. Click "Add Device" to get started.
                                </td>
                            </tr>
                        ) : (
                            devices.map(device => (
                                <tr key={device.id}>
                                    <td><strong>{device.name}</strong></td>
                                    <td>{device.ip_address}</td>
                                    <td>{device.device_type || 'N/A'}</td>
                                    <td>{device.snmp_version}</td>
                                    <td>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                            {device.snmp_modules && device.snmp_modules.map(mod => (
                                                <span key={mod} className="badge" style={{ fontSize: '0.7em', padding: '2px 6px' }}>{mod}</span>
                                            ))}
                                        </div>
                                    </td>
                                    <td>
                                        <span className={`badge badge-${device.enabled ? 'success' : 'danger'}`}>
                                            {device.enabled ? 'Enabled' : 'Disabled'}
                                        </span>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                            <button
                                                className="btn btn-secondary"
                                                style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                                                onClick={() => handleEdit(device)}
                                            >
                                                Edit
                                            </button>
                                            <button
                                                className="btn btn-success"
                                                style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                                                onClick={() => handleCollect(device.id)}
                                            >
                                                Collect
                                            </button>
                                            <button
                                                className="btn btn-danger"
                                                style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                                                onClick={() => handleDelete(device.id)}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Add/Edit Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>{editingDevice ? 'Edit Device' : 'Add Device'}</h3>
                            <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
                        </div>

                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label className="form-label">Device Name *</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    required
                                    placeholder="e.g., Router-01"
                                />
                            </div>

                            <div className="form-row">
                                <div className="form-group">
                                    <label className="form-label">IP Address *</label>
                                    <input
                                        className="input"
                                        type="text"
                                        value={formData.ip_address}
                                        onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                                        required
                                        placeholder="192.168.1.1"
                                    />
                                </div>

                                <div className="form-group">
                                    <label className="form-label">SNMP Port</label>
                                    <input
                                        className="input"
                                        type="number"
                                        value={formData.snmp_port}
                                        onChange={(e) => setFormData({ ...formData, snmp_port: parseInt(e.target.value) })}
                                        placeholder="161"
                                    />
                                </div>
                            </div>

                            <div className="form-row">
                                <div className="form-group">
                                    <label className="form-label">SNMP Version</label>
                                    <select
                                        className="select"
                                        value={formData.snmp_version}
                                        onChange={(e) => setFormData({ ...formData, snmp_version: e.target.value })}
                                    >
                                        <option value="1">v1</option>
                                        <option value="2c">v2c</option>
                                        <option value="3">v3</option>
                                    </select>
                                </div>

                                <div className="form-group">
                                    <label className="form-label">SNMP Modules</label>
                                    <select
                                        className="select"
                                        multiple
                                        size="4"
                                        value={formData.snmp_modules}
                                        onChange={handleModuleChange}
                                        style={{ height: 'auto' }}
                                    >
                                        {availableModules.map(mod => (
                                            <option key={mod} value={mod}>{mod}</option>
                                        ))}
                                    </select>
                                    <small className="text-muted">Hold Ctrl/Cmd to select multiple. Default: if_mib</small>
                                </div>
                            </div>

                            <div className="form-group">
                                <label className="form-label">Device Type</label>
                                <select
                                    className="select"
                                    value={formData.device_type}
                                    onChange={(e) => setFormData({ ...formData, device_type: e.target.value })}
                                >
                                    <option value="router">Router</option>
                                    <option value="switch">Switch</option>
                                    <option value="firewall">Firewall</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label">SNMP Community</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={formData.snmp_community}
                                    onChange={(e) => setFormData({ ...formData, snmp_community: e.target.value })}
                                    placeholder="public"
                                />
                            </div>

                            <div className="form-group">
                                <label className="form-label">Description</label>
                                <input
                                    className="input"
                                    type="text"
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    placeholder="Optional description"
                                />
                            </div>

                            <div className="form-group">
                                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <input
                                        type="checkbox"
                                        checked={formData.enabled}
                                        onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                                    />
                                    <span className="form-label" style={{ margin: 0 }}>Enabled</span>
                                </label>
                            </div>

                            <div className="action-buttons">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary">
                                    {editingDevice ? 'Update' : 'Create'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default DeviceManagement;
