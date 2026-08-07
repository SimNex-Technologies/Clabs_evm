import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import ResultsView from './ResultsView.jsx';

const POLL_MS = 2000;

export default function Dashboard({ token, onLogout }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [results, setResults] = useState(null);
  const [forcePassword, setForcePassword] = useState('');
  const [showForce, setShowForce] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetConfirm, setResetConfirm] = useState('');

  const refresh = useCallback(async () => {
    try {
      const s = await api.getState();
      setState(s);
    } catch {
      // transient - try again on next tick
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  async function guarded(fn) {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      if (e.status === 401) {
        onLogout();
        return;
      }
      setMessage({ type: 'error', text: e.message });
    } finally {
      setBusy(false);
    }
  }

  const handleUnlock = () => guarded(async () => {
    await api.adminUnlock(token, state.test_mode);
  });

  const handleLock = () => guarded(async () => {
    await api.adminLock(token);
  });

  const handlePolling = (action) => guarded(async () => {
    await api.adminPolling(token, action);
  });

  const handleTestMode = (enabled) => guarded(async () => {
    await api.adminTestMode(token, enabled);
  });

  const handleExport = () => guarded(async () => {
    const r = await api.adminExport(token);
    setMessage({ type: 'ok', text: `Exported to ${r.path}` });
  });

  async function handleViewResults() {
    setMessage(null);
    try {
      const r = await api.adminResults(token);
      setResults(r);
    } catch (e) {
      if (e.status === 401) return onLogout();
      if (e.status === 403) {
        setShowForce(true);
      } else {
        setMessage({ type: 'error', text: e.message });
      }
    }
  }

  async function handleForceReveal() {
    try {
      const r = await api.adminResultsForce(token, forcePassword);
      setResults(r);
      setShowForce(false);
      setForcePassword('');
    } catch (e) {
      setMessage({ type: 'error', text: 'Incorrect password.' });
    }
  }

  async function handleReset() {
    if (resetConfirm !== 'RESET') return;
    await guarded(async () => {
      await api.adminReset(token);
    });
    setResults(null);
    setShowReset(false);
    setResetConfirm('');
  }

  if (!state) return <div className="admin-dashboard">Loading…</div>;

  return (
    <div className="admin-dashboard">
      <div className="admin-topbar">
        <h1>C-LABS Digital EVM — Officer Console</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link to="/" className="btn">Voting Kiosk</Link>
          <button className="btn" onClick={onLogout}>Log Out</button>
        </div>
      </div>

      <div className="status-panel">
        <div className="status-light">
          <span className={`dot ${state.status === 'LOCKED' ? 'locked' : 'unlocked'}`} />
          {state.status === 'LOCKED' ? 'LOCKED' : 'UNLOCKED'}
        </div>
        <div className="stat">
          <span className="n">{state.ballot_count}</span>
          <span className="label">Ballots Cast</span>
        </div>
        <div className="stat">
          <span className="n">{state.polling === 'OPEN' ? 'Open' : state.polling === 'CLOSED' ? 'Closed' : 'Not Started'}</span>
          <span className="label">Polling</span>
        </div>
        {state.test_mode && (
          <div className="stat">
            <span className="n" style={{ color: 'var(--amber)' }}>TEST MODE</span>
            <span className="label">Rehearsal ballots excluded from results</span>
          </div>
        )}
      </div>

      {message && (
        <div className={message.type === 'error' ? 'admin-error' : 'status-line'}>
          {message.text}
        </div>
      )}

      <button
        className="big-button unlock-cta"
        onClick={handleUnlock}
        disabled={busy || state.status === 'UNLOCKED' || state.polling !== 'OPEN'}
      >
        {state.status === 'UNLOCKED' ? 'MACHINE READY FOR STUDENT' : 'UNLOCK FOR NEXT STUDENT'}
      </button>
      {state.polling !== 'OPEN' && (
        <p className="status-line">Open polling below before unlocking for students.</p>
      )}

      <div className="panel">
        <h2>Machine Controls</h2>
        <div className="action-row">
          <button className="btn danger" onClick={handleLock} disabled={busy}>Lock Voting</button>
          {state.polling === 'OPEN' ? (
            <button className="btn" onClick={() => handlePolling('close')} disabled={busy}>Close Polling</button>
          ) : (
            <button className="btn primary" onClick={() => handlePolling('open')} disabled={busy}>Open Polling</button>
          )}
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={state.test_mode}
              onChange={(e) => handleTestMode(e.target.checked)}
              disabled={busy}
            />
            Test Mode (rehearsal ballots, excluded from results)
          </label>
        </div>
      </div>

      <div className="panel">
        <h2>Results</h2>
        <div className="action-row" style={{ marginBottom: results ? 16 : 0 }}>
          <button className="btn" onClick={handleViewResults}>Refresh Results</button>
          <button className="btn" onClick={handleExport} disabled={busy}>Export Excel</button>
        </div>
        {showForce && (
          <div className="modal-backdrop" onClick={() => setShowForce(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h2>Results Hidden While Polling Is Open</h2>
              <p className="hint">Re-enter the admin password to view results early.</p>
              <input
                className="admin-input"
                type="password"
                placeholder="Password"
                value={forcePassword}
                onChange={(e) => setForcePassword(e.target.value)}
                autoFocus
              />
              <div className="action-row">
                <button className="btn primary" onClick={handleForceReveal}>Reveal</button>
                <button className="btn" onClick={() => setShowForce(false)}>Cancel</button>
              </div>
            </div>
          </div>
        )}
        {results && <ResultsView tally={results.tally} ballotCount={results.ballot_count} />}
      </div>

      <div className="panel">
        <h2>Danger Zone</h2>
        <button className="btn danger" onClick={() => setShowReset(true)}>Reset Election</button>
        {showReset && (
          <div className="modal-backdrop" onClick={() => setShowReset(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h2>Reset Election</h2>
              <p className="hint">
                This backs up the current database and Excel file, then permanently
                erases all ballots and votes. Type <strong>RESET</strong> to confirm.
              </p>
              <input
                className="admin-input"
                value={resetConfirm}
                onChange={(e) => setResetConfirm(e.target.value)}
                autoFocus
              />
              <div className="action-row">
                <button className="btn danger" onClick={handleReset} disabled={resetConfirm !== 'RESET'}>
                  Back Up & Reset
                </button>
                <button className="btn" onClick={() => setShowReset(false)}>Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
