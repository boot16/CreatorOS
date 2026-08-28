import { useEffect, useState, useCallback } from 'react';
import { api } from './api';

/**
 * Global bootstrap store — one call to /api/v1/me at app mount.
 * Every page can read the current identity + data mode from here.
 */
let state = {
  loaded: false,
  loading: true,
  error: null,
  is_authenticated: false,
  is_demo: false,
  data_mode: 'demo',
  user: null,
  creator: null,
  workspace: null,
  youtube_connected: false,
  youtube_last_synced_at: null,
  dna_status: 'not_computed',
};

const listeners = new Set();

async function load() {
  try {
    const r = await api.get('/v1/me');
    state = { ...state, ...r.data, loaded: true, loading: false, error: null };
  } catch (e) {
    state = { ...state, loaded: true, loading: false, error: e?.message || 'bootstrap failed' };
  }
  listeners.forEach(l => l());
}

let didLoad = false;

export function useBootstrap() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const l = () => setTick(t => t + 1);
    listeners.add(l);
    if (!didLoad) { didLoad = true; load(); }
    return () => listeners.delete(l);
  }, []);
  const reload = useCallback(() => load(), []);
  return { ...state, reload };
}

export async function logout() {
  try { await api.post('/auth/logout'); } catch (e) { /* ignore */ }
  state = { ...state, is_authenticated: false, user: null, creator: null, workspace: null,
             youtube_connected: false, youtube_last_synced_at: null, dna_status: 'not_computed' };
  listeners.forEach(l => l());
  await load();
}
