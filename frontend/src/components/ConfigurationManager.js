import React, { useState, useEffect, useCallback } from 'react';
import { getModules, getConfigs, createConfig, updateConfig, deleteConfig } from '../services/api';
import { useToast } from '../hooks/useToast';

const EMPTY_FORM = { oid: '', oid_name: '', description: '', enabled: true };

export default function ConfigurationManager() {
  const { showToast } = useToast();
  const [modules, setModules] = useState([]);
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [togglingId, setTogglingId] = useState(null);

  const closeModal = () => { setShowModal(false); setForm(EMPTY_FORM); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, c] = await Promise.all([getModules().catch(() => []), getConfigs()]);
      setModules(m);
      setConfigs(c);
    } catch {
      showToast('Failed to load configuration', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (cfg) => {
    setTogglingId(cfg.id);
    try {
      const updated = await updateConfig(cfg.id, { enabled: !cfg.enabled });
      setConfigs(prev => prev.map(c => c.id === cfg.id ? updated : c));
    } catch {
      showToast('Failed to update config', 'error');
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (cfg) => {
    if (!window.confirm(`Delete OID config "${cfg.oid_name}" (${cfg.oid})?`)) return;
    try {
      await deleteConfig(cfg.id);
      setConfigs(prev => prev.filter(c => c.id !== cfg.id));
      showToast('Config deleted', 'success');
    } catch {
      showToast('Failed to delete config', 'error');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await createConfig(form);
      setConfigs(prev => [...prev, created]);
      closeModal();
      showToast(`OID "${form.oid_name}" added`, 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to create config'), 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Configuration</div>
          <div className="page-subtitle">Manage OID collection configs and supported modules</div>
        </div>
      </div>

      {/* OID Collection Configs */}
      <div className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>OID Collection Configs</div>
            <div className="page-subtitle">Which OIDs the agent collects from each device.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Add OID</button>
        </div>
        {configs.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-faint)' }}>
            No OID configs defined. Add one to start collecting metrics.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>OID Name</th>
                <th>OID</th>
                <th>Description</th>
                <th>Enabled</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {configs.map(cfg => (
                <tr key={cfg.id}>
                  <td style={{ fontWeight: 500 }}>{cfg.oid_name}</td>
                  <td className="font-mono text-sm text-muted">{cfg.oid}</td>
                  <td className="text-sm text-muted">{cfg.description || '—'}</td>
                  <td>
                    <span className={`badge ${cfg.enabled ? 'badge-success' : 'badge-danger'}`} style={{ marginRight: 8 }}>
                      {cfg.enabled ? 'Active' : 'Disabled'}
                    </span>
                    <button
                      className={`btn btn-sm ${cfg.enabled ? 'btn-secondary' : 'btn-primary'}`}
                      onClick={() => handleToggle(cfg)}
                      disabled={togglingId === cfg.id}
                    >
                      {cfg.enabled ? 'Disable' : 'Enable'}
                    </button>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(cfg)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Supported Modules */}
      <div className="card">
        <div className="page-title" style={{ fontSize: 13, marginBottom: 4 }}>Supported Modules</div>
        <div className="page-subtitle" style={{ marginBottom: 12 }}>
          SNMP module groups available for collection. Assign modules to devices via Device Management.
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {modules.map(mod => (
            <span key={mod} className="badge" style={{ fontSize: 12, padding: '4px 10px' }}>{mod}</span>
          ))}
        </div>
      </div>

      {/* Add OID Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add OID Collection Config</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">OID</label>
                <input className="input" required placeholder="e.g. 1.3.6.1.2.1.2.2.1.10"
                  value={form.oid}
                  onChange={e => setForm({ ...form, oid: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">OID Name</label>
                <input className="input" required placeholder="e.g. ifInOctets"
                  value={form.oid_name}
                  onChange={e => setForm({ ...form, oid_name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Description (optional)</label>
                <input className="input" placeholder="e.g. Inbound octets per interface"
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.enabled}
                    onChange={e => setForm({ ...form, enabled: e.target.checked })} />
                  <span className="form-label" style={{ margin: 0 }}>Enable immediately</span>
                </label>
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Adding...' : 'Add OID'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
