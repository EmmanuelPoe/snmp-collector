import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    const body = new URLSearchParams({ username: email, password });
    try {
      const resp = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });
      if (!resp.ok) {
        setError('Invalid email or password.');
        setLoading(false);
        return;
      }
      const data = await resp.json();
      if (!data.access_token) {
        setError('Login failed: unexpected server response.');
        setLoading(false);
        return;
      }
      login(data.access_token);
      navigate('/');
    } catch {
      setError('Network error — is the backend running?');
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
          <h2>Sign in</h2>
          <p className="login-form-subtext">Enter your credentials to access the dashboard.</p>

          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="login-field">
              <label className="form-label">Email</label>
              <input
                className="input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="admin@localhost"
                autoComplete="email"
                autoFocus
              />
            </div>

            <div className="login-field">
              <label className="form-label">Password</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary login-submit"
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
