const BASE = '';

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  let body = null;
  try {
    body = await res.json();
  } catch {
    // no body
  }
  if (!res.ok) {
    const err = new Error((body && body.detail) || `Request failed (${res.status})`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

export const api = {
  getState: () => request('/api/state'),
  getBallot: () => request('/api/ballot'),
  castBallot: (ballotId, selections) =>
    request('/api/ballot/cast', {
      method: 'POST',
      body: JSON.stringify({ ballot_id: ballotId, selections }),
    }),

  adminSetup: (password) =>
    request('/api/admin/setup', { method: 'POST', body: JSON.stringify({ password }) }),
  adminLogin: (password) =>
    request('/api/admin/login', { method: 'POST', body: JSON.stringify({ password }) }),

  adminUnlock: (token, isTest) =>
    request('/api/admin/unlock', {
      method: 'POST',
      headers: authHeader(token),
      body: JSON.stringify({ is_test: !!isTest }),
    }),
  adminLock: (token) =>
    request('/api/admin/lock', { method: 'POST', headers: authHeader(token) }),
  adminPolling: (token, action) =>
    request('/api/admin/polling', {
      method: 'POST',
      headers: authHeader(token),
      body: JSON.stringify({ action }),
    }),
  adminTestMode: (token, enabled) =>
    request('/api/admin/test-mode', {
      method: 'POST',
      headers: authHeader(token),
      body: JSON.stringify({ enabled }),
    }),
  adminResults: (token) =>
    request('/api/admin/results', { headers: authHeader(token) }),
  adminResultsForce: (token, password) =>
    request('/api/admin/results/force', {
      method: 'POST',
      headers: authHeader(token),
      body: JSON.stringify({ password }),
    }),
  adminExport: (token) =>
    request('/api/admin/export', { method: 'POST', headers: authHeader(token) }),
  adminReset: (token) =>
    request('/api/admin/reset', {
      method: 'POST',
      headers: authHeader(token),
      body: JSON.stringify({ confirm: 'RESET' }),
    }),
};

function authHeader(token) {
  return { Authorization: `Bearer ${token}` };
}
