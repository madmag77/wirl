// Environment constants
const {
  VITE_API_BASE_URL,
  VITE_POLL_INTERVAL_MS,
} = import.meta.env;

export const API_BASE_URL = VITE_API_BASE_URL || 'http://localhost:8000';
export const POLL_INTERVAL_MS = parseInt(VITE_POLL_INTERVAL_MS, 10) || 10000;
