import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { changePassword } from '../services/api';

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (newPassword !== confirm) {
      setError('New passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to change password.');
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-brand-panel">
        <div className="login-brand-content">
          <div className="login-brand-icon">⬡</div>
          <div className="login-brand-name">SNMP Monitor</div>
          <div className="login-brand-tagline">Infrastructure visibility at scale.</div>
        </div>
      </div>

      <div className="login-form-panel">
        <div className="login-form-card">
          <h2>Change Password</h2>
          <p className="login-form-subtext">You must set a new password before continuing.</p>

          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="login-field">
              <label className="form-label">Current Password</label>
              <input
                className="input"
                type="password"
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="login-field">
              <label className="form-label">New Password</label>
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                required
                placeholder="min 8 characters"
              />
            </div>
            <div className="login-field">
              <label className="form-label">Confirm New Password</label>
              <input
                className="input"
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                required
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary login-submit"
              disabled={loading}
            >
              {loading ? 'Saving...' : 'Set New Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
