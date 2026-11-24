// Build-time configuration (Vite env vars). See .env.example for production notes about tile providers.
const env = (typeof import.meta !== 'undefined' && import.meta.env) || {};

export const API_BASE = (env.VITE_API_BASE ?? '/api').replace(/\/$/, '');

export const TILES = {
  street: {
    url: env.VITE_TILE_STREET_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: env.VITE_TILE_STREET_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  satellite: {
    url: env.VITE_TILE_SATELLITE_URL || 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: env.VITE_TILE_SATELLITE_ATTRIBUTION || 'Imagery &copy; Esri, Maxar, Earthstar Geographics and the GIS User Community',
    maxZoom: 18,
  },
};

// Colours of the potential classes are the ones the API sends in /meta; these are only the fallback.
export const FALLBACK_LEGEND = [
  { key: 'high', color: '#1E6FD9' },
  { key: 'moderate', color: '#2E9E4F' },
  { key: 'low', color: '#F2C230' },
  { key: 'very_low', color: '#D64545' },
  { key: 'insufficient_data', color: '#9AA3AD' },
];
