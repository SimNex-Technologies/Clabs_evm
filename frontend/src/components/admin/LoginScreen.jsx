'use client';

import { useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api.js';

export default function LoginScreen({ onAuthenticated }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { token } = await api.adminLogin(password);
      onAuthenticated(token);
    } catch (e2) {
      setError(e2.status === 401 ? 'Incorrect password.' : e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-card">
      <h1>Election Officer Login</h1>
      <p className="hint">Enter the admin password to manage voting.</p>
      <form onSubmit={handleSubmit}>
        <input
          className="admin-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
        />
        {error && <div className="admin-error">{error}</div>}
        <button className="btn primary" type="submit" disabled={busy} style={{ width: '100%', padding: 16 }}>
          {busy ? 'Signing in…' : 'Log In'}
        </button>
      </form>
      <p style={{ marginTop: 16 }}>
        <Link href="/" style={{ color: 'var(--muted)', fontSize: 14 }}>← Back to voting kiosk</Link>
      </p>
    </div>
  );
}
