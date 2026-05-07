import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    const body = new URLSearchParams({ username: email, password });
    try {
      const resp = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });
      if (!resp.ok) {
        setError('Invalid email or password');
        return;
      }
      const data = await resp.json();
      login(data.access_token);
      navigate('/');
    } catch {
      setError('Network error — is the backend running?');
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: '120px auto', padding: '2rem', border: '1px solid #ccc', borderRadius: 8 }}>
      <h2>SNMP Collector Login</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label>Email<br />
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required style={{ width: '100%' }} />
          </label>
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label>Password<br />
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required style={{ width: '100%' }} />
          </label>
        </div>
        <button type="submit" style={{ width: '100%' }}>Sign In</button>
      </form>
    </div>
  );
}
