import { useEffect, useState, useCallback } from 'react';
import { api } from './api';

let cache = new Set();
const listeners = new Set();
let loaded = false;

async function load() {
  const r = await api.get('/shortlist');
  cache = new Set(r.data.map(x => x.opportunity_id));
  loaded = true;
  listeners.forEach(l => l());
}

export function useShortlist() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const l = () => setTick(t => t + 1);
    listeners.add(l);
    if (!loaded) load();
    return () => listeners.delete(l);
  }, []);

  const isSaved = useCallback((id) => cache.has(id), []);
  const toggle = useCallback(async (id) => {
    if (cache.has(id)) {
      cache.delete(id);
      listeners.forEach(l => l());
      await api.delete(`/shortlist/${id}`);
    } else {
      cache.add(id);
      listeners.forEach(l => l());
      await api.post('/shortlist', { opportunity_id: id });
    }
  }, []);
  return { isSaved, toggle, count: cache.size };
}

export async function refreshShortlist() { await load(); }
