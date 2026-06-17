import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getDevices, walkDevice, getWalkResult, createConfig } from '../services/api';
import { useToast } from '../hooks/useToast';

const DEFAULT_OID = '1.3.6.1.2.1';
const POLL_MS = 2000;
const MAX_POLLS = 20;

export default function MibBrowser() {
  const { showToast } = useToast();
  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState('');
  const [baseOid, setBaseOid] = useState(DEFAULT_OID);
  const [walking, setWalking] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      setDevices(await getDevices(true));
    } catch {
      showToast('Failed to load devices', 'error');
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => () => { if (pollRef.current) clearTimeout(pollRef.current); }, []);

  const handleWalk = async (e) => {
    e.preventDefault();
    if (!deviceId) return;
    setWalking(true);
    setResults(null);
    setError(null);
    try {
      const { command_id } = await walkDevice(deviceId, baseOid || DEFAULT_OID);
      let polls = 0;
      const poll = async () => {
        polls += 1;
        try {
          const r = await getWalkResult(command_id);
          if (r.status === 'done') {
            setResults(r.result || []);
            setWalking(false);
          } else if (r.status === 'error') {
            setError(r.error || 'Walk failed');
            setWalking(false);
          } else if (polls >= MAX_POLLS) {
            setError('Walk timed out — is the agent online?');
            setWalking(false);
          } else {
            pollRef.current = setTimeout(poll, POLL_MS);
          }
        } catch {
          setError('Failed to retrieve walk result');
          setWalking(false);
        }
      };
      pollRef.current = setTimeout(poll, POLL_MS);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start walk');
      setWalking(false);
    }
  };

  const handleAdd = async (oid) => {
    const name = window.prompt(`Name for OID ${oid}:`, '');
    if (!name) return;
    try {
      await createConfig({ oid, oid_name: name, enabled: true });
      showToast(`Added ${name} to collection`, 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to add OID'), 'error');
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">MIB Browser</div>
          <div className="page-subtitle">Walk a device's OID tree and add OIDs to the collection</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <form onSubmit={handleWalk} style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Device</label>
            <select className="select" value={deviceId} onChange={e => setDeviceId(e.target.value)} required style={{ minWidth: 220 }}>
              <option value="">Select device...</option>
              {devices.map(d => <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0, flex: 1, minWidth: 220 }}>
            <label className="form-label">Base OID</label>
            <input className="input" value={baseOid} onChange={e => setBaseOid(e.target.value)} placeholder={DEFAULT_OID} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={walking || !deviceId}>
            {walking ? 'Walking…' : 'Walk'}
          </button>
        </form>
      </div>

      {error && (
        <div className="card" style={{ marginBottom: 16, color: 'var(--color-error)' }}>{error}</div>
      )}

      {results && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--color-border)' }}>
            <div className="page-title" style={{ fontSize: 13 }}>{results.length} OIDs</div>
          </div>
          {results.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-faint)' }}>No OIDs returned.</div>
          ) : (
            <table className="table">
              <thead><tr><th>OID</th><th>Value</th><th>Actions</th></tr></thead>
              <tbody>
                {results.map((row, i) => (
                  <tr key={i}>
                    <td className="font-mono text-sm">{row.oid}</td>
                    <td className="text-sm text-muted" style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.value}</td>
                    <td><button className="btn btn-sm btn-secondary" onClick={() => handleAdd(row.oid)}>+ Add</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
