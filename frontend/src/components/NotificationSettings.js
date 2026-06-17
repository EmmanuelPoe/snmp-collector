import React, { useState, useEffect, useCallback } from 'react';
import {
  getNotificationChannels, createNotificationChannel,
  updateNotificationChannel, deleteNotificationChannel,
} from '../services/api';
import { useToast } from '../hooks/useToast';

const SEVERITIES = ['critical', 'warning', 'info'];
const EMPTY_FORM = { name: '', type: 'slack', url: '', severity_filter: [...SEVERITIES], enabled: true };

export default function NotificationSettings() {
  const { showToast } = useToast();
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [togglingId, setTogglingId] = useState(null);

  const closeModal = () => { setShowModal(false); setForm(EMPTY_FORM); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setChannels(await getNotificationChannels());
    } catch {
      showToast('Failed to load notification channels', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const toggleSeverity = (sev) => {
    setForm(f => ({
      ...f,
      severity_filter: f.severity_filter.includes(sev)
        ? f.severity_filter.filter(s => s !== sev)
        : [...f.severity_filter, sev],
    }));
  };

  const handleToggle = async (ch) => {
    setTogglingId(ch.id);
    try {
      const updated = await updateNotificationChannel(ch.id, { enabled: !ch.enabled });
      setChannels(prev => prev.map(c => c.id === ch.id ? updated : c));
    } catch {
      showToast('Failed to update channel', 'error');
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (ch) => {
    if (!window.confirm(`Delete notification channel "${ch.name}"?`)) return;
    try {
      await deleteNotificationChannel(ch.id);
      setChannels(prev => prev.filter(c => c.id !== ch.id));
      showToast('Channel deleted', 'success');
    } catch {
      showToast('Failed to delete channel', 'error');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await createNotificationChannel(form);
      setChannels(prev => [...prev, created]);
      closeModal();
      showToast(`Channel "${form.name}" added`, 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to create channel'), 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Notifications</div>
          <div className="page-subtitle">Send alerts to Slack or a generic webhook</div>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>Notification Channels</div>
            <div className="page-subtitle">New alerts are POSTed to each enabled channel matching the alert severity.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Add Channel</button>
        </div>
        {channels.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-faint)' }}>
            No channels configured. Add one to start receiving alert notifications.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>URL</th>
                <th>Severities</th>
                <th>Enabled</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {channels.map(ch => (
                <tr key={ch.id}>
                  <td style={{ fontWeight: 500 }}>{ch.name}</td>
                  <td><span className="badge">{ch.type}</span></td>
                  <td className="font-mono text-sm text-muted" style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ch.url}</td>
                  <td className="text-sm text-muted">{(ch.severity_filter && ch.severity_filter.length) ? ch.severity_filter.join(', ') : 'all'}</td>
                  <td>
                    <span className={`badge ${ch.enabled ? 'badge-success' : 'badge-danger'}`} style={{ marginRight: 8 }}>
                      {ch.enabled ? 'Active' : 'Disabled'}
                    </span>
                    <button
                      className={`btn btn-sm ${ch.enabled ? 'btn-secondary' : 'btn-primary'}`}
                      onClick={() => handleToggle(ch)}
                      disabled={togglingId === ch.id}
                    >
                      {ch.enabled ? 'Disable' : 'Enable'}
                    </button>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(ch)}>Delete</button>
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
              <h3>Add Notification Channel</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Name</label>
                <input className="input" required placeholder="e.g. ops-alerts"
                  value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="input" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
                  <option value="slack">Slack</option>
                  <option value="webhook">Generic webhook</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">{form.type === 'slack' ? 'Slack incoming webhook URL' : 'Webhook URL'}</label>
                <input className="input" required placeholder="https://..."
                  value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Severities</label>
                <div style={{ display: 'flex', gap: 12 }}>
                  {SEVERITIES.map(sev => (
                    <label key={sev} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', textTransform: 'capitalize' }}>
                      <input type="checkbox" checked={form.severity_filter.includes(sev)} onChange={() => toggleSeverity(sev)} />
                      <span className="text-sm">{sev}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Adding...' : 'Add Channel'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
