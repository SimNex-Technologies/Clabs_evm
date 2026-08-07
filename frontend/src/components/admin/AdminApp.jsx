'use client';

import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import SetupScreen from './SetupScreen.jsx';
import LoginScreen from './LoginScreen.jsx';
import Dashboard from './Dashboard.jsx';

const TOKEN_KEY = 'clabs_evm_admin_token';

export default function AdminApp() {
  const [adminConfigured, setAdminConfigured] = useState(null); // null = loading
  const [token, setToken] = useState(null);

  useEffect(() => {
    setToken(sessionStorage.getItem(TOKEN_KEY));
    api.getState().then((s) => setAdminConfigured(s.admin_configured)).catch(() => {});
  }, []);

  function handleAuthenticated(newToken) {
    sessionStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
  }

  function handleLogout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }

  if (adminConfigured === null) {
    return <div className="admin" />;
  }

  if (!adminConfigured) {
    return (
      <div className="admin">
        <SetupScreen onAuthenticated={(t) => { setAdminConfigured(true); handleAuthenticated(t); }} />
      </div>
    );
  }

  if (!token) {
    return (
      <div className="admin">
        <LoginScreen onAuthenticated={handleAuthenticated} />
      </div>
    );
  }

  return (
    <div className="admin">
      <Dashboard token={token} onLogout={handleLogout} />
    </div>
  );
}
