import { API_BASE } from './config.js';

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { params, signal, method = 'GET', body } = {}) {
  const url = new URL(API_BASE + path, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  });
  let res;
  try {
    res = await fetch(url, {
      method, signal, referrerPolicy: 'no-referrer',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError(0, 'network');
  }
  if (!res.ok) {
    let detail = null;
    try { detail = (await res.json()).detail; } catch { /* not JSON */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const api = {
  meta: (signal) => request('/meta', { signal }),
  datasets: (signal) => request('/datasets', { signal }),
  analyze: ({ lat, lon, accuracy }, signal) =>
    request('/analyze', { params: { lat: lat.toFixed(6), lon: lon.toFixed(6), accuracy_m: accuracy ? Math.round(accuracy) : undefined }, signal }),
  rankPlot: (boundary, signal) => request('/plot-rank', { method: 'POST', body: { boundary, grid_size: 3 }, signal }),
  explainWithAI: (report, language = 'en') => request('/ai/explain', { method: 'POST', body: { report, language } }),
  search: (q, signal) => request('/search', { params: { q, limit: 8 }, signal }),
  regions: (level, parentId, signal) => request('/regions', { params: { level, parent_id: parentId }, signal }),
  layer: (name, bbox, signal) => request(`/layers/${name}`, { params: { bbox: bbox.map((v) => v.toFixed(4)).join(',') }, signal }),
  coverage: (signal) => request('/layers/coverage', { signal }),
  contact: (body) => request('/contact', { method: 'POST', body }),
};

/** Same-origin URLs for the printable report (HTML always works; PDF needs WeasyPrint on the server). */
export function reportUrl(kind, { lat, lon, accuracy }, lang) {
  const q = new URLSearchParams({ lat: lat.toFixed(6), lon: lon.toFixed(6), lang });
  if (accuracy) q.set('accuracy_m', String(Math.round(accuracy)));
  return `${API_BASE}/report/${kind}?${q}`;
}
