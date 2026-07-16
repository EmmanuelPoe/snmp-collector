import React, { useState, useEffect, useCallback } from 'react';
import { getAuditLog } from '../services/api';
import { useToast } from '../hooks/useToast';

const PAGE_SIZE = 50;
const EMPTY_FILTERS = { actor_email: '', action: '', target_type: '' };

export default function AuditPage() {
  const { showToast } = useToast();
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const data = await getAuditLog(params);
      setEntries(data.items);
      setTotal(data.total);
    } catch {
      showToast('Failed to load audit log', 'error');
    } finally {
      setLoading(false);
    }
  }, [page, filters, showToast]);

  useEffect(() => { load(); }, [load]);

  const setFilter = (key) => (e) => {
    setPage(0);
    setFilters(f => ({ ...f, [key]: e.target.value }));
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Log</h1>
          <p className="page-subtitle">Who did what, when, and from where</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <input
            className="input"
            style={{ maxWidth: 220 }}
            placeholder="Filter by actor email"
            value={filters.actor_email}
            onChange={setFilter('actor_email')}
          />
          <input
            className="input"
            style={{ maxWidth: 220 }}
            placeholder="Filter by action (e.g. auth.login)"
            value={filters.action}
            onChange={setFilter('action')}
          />
          <input
            className="input"
            style={{ maxWidth: 180 }}
            placeholder="Filter by target type"
            value={filters.target_type}
            onChange={setFilter('target_type')}
          />
        </div>
      </div>

      {loading ? (
        <div className="loading-state">Loading audit log...</div>
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Target</th>
                <th>Details</th>
                <th>Source IP</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', opacity: 0.7 }}>No audit entries match</td></tr>
              )}
              {entries.map(e => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</td>
                  <td>{e.actor_email || '—'}</td>
                  <td><code>{e.action}</code></td>
                  <td>{e.target_type ? `${e.target_type} #${e.target_id}` : '—'}</td>
                  <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={e.summary ? JSON.stringify(e.summary) : undefined}>
                    {e.summary ? JSON.stringify(e.summary) : '—'}
                  </td>
                  <td>{e.source_ip || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
            <span style={{ opacity: 0.7 }}>{total} entries</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button className="btn btn-secondary" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                ‹ Prev
              </button>
              <span>Page {page + 1} of {pageCount}</span>
              <button className="btn btn-secondary" disabled={page + 1 >= pageCount} onClick={() => setPage(p => p + 1)}>
                Next ›
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
