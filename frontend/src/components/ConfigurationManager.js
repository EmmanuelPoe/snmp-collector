import React, { useState, useEffect } from 'react';
import {
  getDevices, getSchedules, updateSchedule, createSchedule,
  reloadConfig, getModules, getModuleConfig, updateModuleConfig
} from '../services/api';
import { useToast } from '../hooks/useToast';

export default function ConfigurationManager() {
  const { showToast } = useToast();
  const [modules, setModules] = useState([]);
  const [devices, setDevices] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newSchedule, setNewSchedule] = useState({ device_id: '', interval_seconds: 60, enabled: true });
  const [selectedModule, setSelectedModule] = useState('');
  const [yamlContent, setYamlContent] = useState('');
  const [originalYaml, setOriginalYaml] = useState('');
  const [editorStatus, setEditorStatus] = useState('');

  useEffect(() => { loadInitialData(); }, []);

  useEffect(() => {
    if (selectedModule) loadModuleConfig(selectedModule);
    else { setYamlContent(''); setOriginalYaml(''); }
  }, [selectedModule]);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [modulesData, devicesData, schedulesData] = await Promise.all([
        getModules(), getDevices(), getSchedules()
      ]);
      setModules(modulesData);
      setDevices(devicesData);
      setSchedules(schedulesData);
      if (modulesData.length > 0) setSelectedModule(modulesData[0]);
    } catch {
      showToast('Failed to load configuration', 'error');
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
    } catch {
      setEditorStatus('error');
      showToast('Failed to load module configuration', 'error');
    }
  };

  const handleSaveModule = async () => {
    setEditorStatus('saving');
    try {
      await updateModuleConfig(selectedModule, yamlContent);
      setOriginalYaml(yamlContent);
      setEditorStatus('');
      showToast(`Module "${selectedModule}" saved`, 'success');
    } catch (err) {
      setEditorStatus('error');
      showToast('Save failed: ' + (err.response?.data?.detail || err.message), 'error');
    }
  };

  const handleToggleSchedule = async (deviceId, sched) => {
    try {
      const updated = await updateSchedule(deviceId, { enabled: !sched.enabled });
      setSchedules(prev => prev.map(s => s.device_id === deviceId ? updated : s));
      showToast(`Schedule ${updated.enabled ? 'resumed' : 'paused'}`, 'success');
    } catch {
      showToast('Failed to update schedule', 'error');
    }
  };

  const handleIntervalChange = async (deviceId, interval) => {
    try {
      const updated = await updateSchedule(deviceId, { interval_seconds: parseInt(interval) });
      setSchedules(prev => prev.map(s => s.device_id === deviceId ? updated : s));
    } catch {
      showToast('Failed to update interval', 'error');
    }
  };

  const handleCreateSchedule = async (e) => {
    e.preventDefault();
    try {
      const created = await createSchedule(newSchedule);
      setSchedules(prev => [...prev, created]);
      setShowModal(false);
      setNewSchedule({ device_id: '', interval_seconds: 60, enabled: true });
      showToast('Schedule created', 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to create schedule'), 'error');
    }
  };

  const handleReloadConfig = async () => {
    try {
      await reloadConfig();
      showToast('Exporter reloaded successfully', 'success');
    } catch {
      showToast('Reload failed', 'error');
    }
  };

  const getDeviceSchedule = (deviceId) => schedules.find(s => s.device_id === deviceId);
  const availableDevices = devices.filter(d => !getDeviceSchedule(d.id));

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Configuration</div>
          <div className="page-subtitle">Collection schedules and SNMP module definitions</div>
        </div>
      </div>

      {/* Schedules */}
      <div className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>Device Collection Schedules</div>
            <div className="page-subtitle">Manage polling intervals and pause/resume collection.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)} disabled={availableDevices.length === 0}>
            + Add Schedule
          </button>
        </div>
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
                  <td style={{ fontWeight: 500 }}>{device.name}</td>
                  <td className="font-mono text-sm text-muted">{device.ip_address}</td>
                  <td>
                    {sched ? (
                      <select className="select" style={{ padding: '0.2rem 0.5rem', width: 'auto', fontSize: 12 }}
                        value={sched.interval_seconds}
                        onChange={e => handleIntervalChange(device.id, e.target.value)}>
                        <option value="30">30s</option>
                        <option value="60">1m</option>
                        <option value="300">5m</option>
                        <option value="900">15m</option>
                        <option value="3600">1h</option>
                      </select>
                    ) : <span className="text-faint text-sm">Not scheduled</span>}
                  </td>
                  <td>
                    {sched ? (
                      <span className={`badge ${sched.enabled ? 'badge-success' : 'badge-danger'}`}>
                        {sched.enabled ? 'Active' : 'Paused'}
                      </span>
                    ) : <span className="badge" style={{ color: 'var(--color-text-faint)', borderColor: 'var(--color-border)' }}>None</span>}
                  </td>
                  <td className="text-sm text-muted">
                    {sched?.last_collection ? new Date(sched.last_collection).toLocaleString() : 'Never'}
                  </td>
                  <td>
                    {sched ? (
                      <button className={`btn btn-sm ${sched.enabled ? 'btn-secondary' : 'btn-primary'}`}
                        onClick={() => handleToggleSchedule(device.id, sched)}>
                        {sched.enabled ? 'Pause' : 'Resume'}
                      </button>
                    ) : (
                      <button className="btn btn-primary btn-sm"
                        onClick={() => { setNewSchedule({ ...newSchedule, device_id: device.id }); setShowModal(true); }}>
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

      {/* Add Schedule Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Configure Collection Schedule</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleCreateSchedule}>
              <div className="form-group">
                <label className="form-label">Device</label>
                <select className="select" required value={newSchedule.device_id}
                  onChange={e => setNewSchedule({ ...newSchedule, device_id: e.target.value })}>
                  <option value="">Select a device...</option>
                  {availableDevices.map(d => (
                    <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>
                  ))}
                  {newSchedule.device_id && !availableDevices.find(d => d.id === parseInt(newSchedule.device_id)) && (
                    <option value={newSchedule.device_id}>
                      {devices.find(d => d.id === parseInt(newSchedule.device_id))?.name}
                    </option>
                  )}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Polling Interval</label>
                <select className="select" value={newSchedule.interval_seconds}
                  onChange={e => setNewSchedule({ ...newSchedule, interval_seconds: parseInt(e.target.value) })}>
                  <option value="30">30 Seconds</option>
                  <option value="60">1 Minute</option>
                  <option value="300">5 Minutes</option>
                  <option value="900">15 Minutes</option>
                  <option value="3600">1 Hour</option>
                </select>
              </div>
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={newSchedule.enabled}
                    onChange={e => setNewSchedule({ ...newSchedule, enabled: e.target.checked })} />
                  <span className="form-label" style={{ margin: 0 }}>Enable collection immediately</span>
                </label>
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={!newSchedule.device_id}>Create Schedule</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Module Editor */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>Module Definitions</div>
            <div className="page-subtitle">Edit YAML configuration for SNMP modules.</div>
          </div>
          <select className="select" style={{ width: 200 }} value={selectedModule}
            onChange={e => setSelectedModule(e.target.value)}>
            {modules.map(mod => <option key={mod} value={mod}>{mod}</option>)}
          </select>
        </div>
        <textarea
          className="code-editor"
          value={yamlContent}
          onChange={e => setYamlContent(e.target.value)}
          spellCheck="false"
          disabled={editorStatus === 'loading' || editorStatus === 'saving'}
        />
        <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-secondary"
            onClick={() => setYamlContent(originalYaml)}
            disabled={yamlContent === originalYaml || editorStatus === 'saving'}>
            Reset
          </button>
          <button className="btn btn-primary"
            onClick={handleSaveModule}
            disabled={yamlContent === originalYaml || editorStatus === 'saving'}>
            {editorStatus === 'saving' ? 'Saving...' : 'Apply Changes'}
          </button>
        </div>
      </div>

      {/* System Maintenance */}
      <div className="card" style={{ background: 'rgba(251,146,60,0.04)', borderColor: 'var(--color-warning-border)' }}>
        <div className="page-title" style={{ fontSize: 13, color: 'var(--color-warning)', marginBottom: 4 }}>
          System Maintenance
        </div>
        <div className="page-subtitle" style={{ marginBottom: 14 }}>
          Use these tools only when manual intervention is required.
        </div>
        <button className="btn btn-warning" onClick={handleReloadConfig}>
          Reload SNMP Exporter Service
        </button>
      </div>
    </div>
  );
}
