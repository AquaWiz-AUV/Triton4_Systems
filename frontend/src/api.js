import axios from 'axios';

// API base URL - set VITE_API_BASE_URL in .env for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchTrajectory = async (mid) => {
  const response = await api.get(`/telemetry/trajectory/${mid}?format=geojson`);
  return response.data;
};

export const fetchLatestTelemetry = async (mid) => {
  const response = await api.get(`/telemetry/latest/${mid}`);
  return response.data;
};

export const sendCommand = async (mid, command, args = {}) => {
  const response = await api.post('/commands', {
    mid,
    cmd: command,
    args,
  });
  return response.data;
};

export const resetDatabase = async () => {
  const response = await api.post('/admin/reset-db');
  return response.data;
};

export default api;
