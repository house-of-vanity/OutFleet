import axios from 'axios';

const VITE_API_BASE = import.meta.env.VITE_API_BASE;
const VITE_API_HOST = import.meta.env.VITE_API_HOST;
const VITE_API_PORT = import.meta.env.VITE_API_PORT;

export const api = axios.create({
  baseURL: `${VITE_API_HOST}:${VITE_API_PORT}${VITE_API_BASE}`,
});
