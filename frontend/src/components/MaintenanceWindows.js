import React, { useState, useEffect, useCallback } from 'react';
import {
  getMaintenanceWindows, createMaintenanceWindow, deleteMaintenanceWindow, getDevices,
} from '../services/api';
import { useToast } from '../hooks/useToast';

function _localToIso(local) {
  // datetime-local value (no tz) -> ISO with the browser's offset
  return new Date(local).toISOString();
}

function _defaultForm() {
  const now = new Date();
  const inHour = new Date(now.getTime() + 60 * 60 * 1000);
  const fmt = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  return { device_id: '', start_at: fmt(now), end_at: fmt(inHour), reason: '' };
}

export default function MaintenanceWindows() {
  const { showToast } = useToast();
  const [windows, setWindows] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(_defaultForm());
  const [saving, setSaving] = useState(false);

  const closeModal = () => { setShowModal(false); setForm(_defaultForm()); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [w, d] = await Promise.all([getMaintenanceWindows(), getDevices().catch(() => [])]);
      setWindows(w);
      setDevices(d);
    } catch {
      showToast('Failed to load maintenance windows', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const deviceName = (id) => {
    if (id === null || id === undefined) return 'All devices';
    const d = devices.find(x => x.id === id);
    return d ? d.name : `Device ${id}`;
  };

  const isActive = (w) => {
    const now = Date.now();
    return new Date(w.start_at).getTime() <= now && new Date(w.end_at).getTime() >= now;
  };

  const handleDelete = async (w) => {
    if (!window.confirm(`Delete maintenance window for ${deviceName(w.device_id)}?`)) return;
    try {
      await deleteMaintenanceWindow(w.id);
      setWindows(prev => prev.filter(x => x.id !== w.id));
      showToast('Window deleted', 'success');
    } catch {
      showToast('Failed to delete window', 'error');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        device_id: form.device_id === '' ? null : Number(form.device_id),
        start_at: _localToIso(form.start_at),
        end_at: _localToIso(form.end_at),
        reason: form.reason || null,
      };
      const created = await createMaintenanceWindow(payload);
      setWindows(prev => [created, ...prev]);
      closeModal();
      showToast('Maintenance window scheduled', 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to schedule window'), 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Maintenance</div>
          <div className="page-subtitle">Suppress new alerts during planned downtime</div>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>Maintenance Windows</div>
            <div className="page-subtitle">New alerts are suppressed for the selected device (or all devices) while a window is active. Open alerts still resolve normally.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Schedule Maintenance</button>
        </div>
        {windows.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-faint)' }}>
            No maintenance windows scheduled.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Start</th>
                <th>End</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {windows.map(w => (
                <tr key={w.id}>
                  <td style={{ fontWeight: 500 }}>{deviceName(w.device_id)}</td>
                  <td className="text-sm text-muted">{new Date(w.start_at).toLocaleString()}</td>
                  <td className="text-sm text-muted">{new Date(w.end_at).toLocaleString()}</td>
                  <td className="text-sm text-muted">{w.reason || '—'}</td>
                  <td>
                    <span className={`badge ${isActive(w) ? 'badge-warning' : ''}`}>
                      {isActive(w) ? 'Active' : (new Date(w.start_at).getTime() > Date.now() ? 'Scheduled' : 'Ended')}
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(w)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Schedule Maintenance</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Scope</label>
                <select className="input" value={form.device_id} onChange={e => setForm({ ...form, device_id: e.target.value })}>
                  <option value="">All devices (global)</option>
                  {devices.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Start</label>
                <input className="input" type="datetime-local" required
                  value={form.start_at} onChange={e => setForm({ ...form, start_at: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">End</label>
                <input className="input" type="datetime-local" required
                  value={form.end_at} onChange={e => setForm({ ...form, end_at: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Reason (optional)</label>
                <input className="input" placeholder="e.g. firmware upgrade"
                  value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} />
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Scheduling...' : 'Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
