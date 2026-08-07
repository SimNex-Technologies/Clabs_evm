import { useState } from 'react';
import { api } from '../api.js';

export default function SetupScreen({ onAuthenticated }) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      const { token } = await api.adminSetup(password);
      onAuthenticated(token);
    } catch (e2) {
      setError(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-card">
      <h1>Set Up Election Officer Password</h1>
      <p className="hint">
        This is the first time the machine has run. Choose a password only the
        election officer will know - it protects unlock, results, and reset.
      </p>
      <form onSubmit={handleSubmit}>
        <input
          className="admin-input"
          type="password"
          placeholder="New password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
        />
        <input
          className="admin-input"
          type="password"
          placeholder="Confirm password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {error && <div className="admin-error">{error}</div>}
        <button className="btn primary" type="submit" disabled={busy} style={{ width: '100%', padding: 16 }}>
          {busy ? 'Setting up…' : 'Set Password & Continue'}
        </button>
      </form>
    </div>
  );
}
