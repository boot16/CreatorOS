import axios from 'axios';

const configuredBackend = (process.env.REACT_APP_BACKEND_URL || '').trim().replace(/\/$/, '');
const isLocalBrowser = typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname);

// Local development must talk to the FastAPI server directly. If the CRA env var
// is missing or accidentally still points at an Emergent preview host, fall back
// to the local backend so auth/status and OAuth navigation do not hit port 3000.
const BACKEND_URL = isLocalBrowser ? 'http://localhost:8000' : configuredBackend;

if (!BACKEND_URL) {
  throw new Error('REACT_APP_BACKEND_URL is required outside local development');
}

export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 60000, withCredentials: true });

export const DEMO_CREATOR_ID = 'alex-morgan';
export const SECOND_CREATOR_ID = 'sarah-chen';
