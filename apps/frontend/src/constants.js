// Environment constants
const {
  VITE_API_BASE_URL,
  VITE_POLL_INTERVAL_MS,
} = import.meta.env;

// Dynamic API base URL that uses the same host as the frontend
const getApiBaseUrl = () => {
  if (VITE_API_BASE_URL) {
    return VITE_API_BASE_URL;
  }

  // Use the same host as the frontend but port 8000 for the backend
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  return `${protocol}//${hostname}:8000`;
};

export const API_BASE_URL = getApiBaseUrl();
export const POLL_INTERVAL_MS = parseInt(VITE_POLL_INTERVAL_MS, 10) || 10000;
