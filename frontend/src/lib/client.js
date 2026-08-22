import { api } from './api';

const KEY = 'creatoros-client-id';

export function getClientId() {
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = (crypto.randomUUID?.() || String(Date.now() + Math.random()));
    localStorage.setItem(KEY, id);
  }
  return id;
}

// Attach header to every axios request
api.interceptors.request.use((cfg) => {
  cfg.headers['X-Client-Id'] = getClientId();
  return cfg;
});
