import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 60000, withCredentials: true });

export const DEMO_CREATOR_ID = 'alex-morgan';
export const SECOND_CREATOR_ID = 'sarah-chen';
