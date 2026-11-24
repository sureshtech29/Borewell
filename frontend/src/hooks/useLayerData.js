import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

const MAX_SPAN = 5.5;     // the API refuses bboxes wider than 6 degrees
const snap = (v, f) => Math.floor(v / f) * f;

/** bbox [minLon, minLat, maxLon, maxLat] around the viewport: padded, snapped outward to 0.05 deg, capped in size. */
export function viewportBox(bounds) {
  const pad = 0.15;
  const w = bounds.getEast() - bounds.getWest(), h = bounds.getNorth() - bounds.getSouth();
  let x0 = bounds.getWest() - w * pad, x1 = bounds.getEast() + w * pad;
  let y0 = bounds.getSouth() - h * pad, y1 = bounds.getNorth() + h * pad;
  if (x1 - x0 > MAX_SPAN) { const c = (x0 + x1) / 2; x0 = c - MAX_SPAN / 2; x1 = c + MAX_SPAN / 2; }
  if (y1 - y0 > MAX_SPAN) { const c = (y0 + y1) / 2; y0 = c - MAX_SPAN / 2; y1 = c + MAX_SPAN / 2; }
  return [snap(x0, 0.05), snap(y0, 0.05), snap(x1, 0.05) + 0.05, snap(y1, 0.05) + 0.05];
}

const contains = (outer, inner) => outer[0] <= inner[0] && outer[1] <= inner[1] && outer[2] >= inner[2] && outer[3] >= inner[3];

/** Loads a GeoJSON layer for the current viewport. Re-fetches only when the viewport leaves the loaded box. */
export function useLayerData(name, bounds, enabled) {
  const [state, setState] = useState({ data: null, box: null, status: 'idle' });
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    if (!enabled || !bounds) return undefined;
    const need = viewportBox(bounds);
    const cur = stateRef.current;
    if (cur.box && cur.status === 'ready' && contains(cur.box, need)) return undefined;
    const ac = new AbortController();
    const timer = setTimeout(() => {
      setState((s) => ({ ...s, status: 'loading' }));
      api.layer(name, need, ac.signal)
        .then((data) => setState({ data, box: need, status: 'ready' }))
        .catch((e) => { if (e.name !== 'AbortError') setState({ data: null, box: null, status: 'error' }); });
    }, 250);
    return () => { clearTimeout(timer); ac.abort(); };
  }, [name, bounds, enabled]);

  return enabled ? state : { data: null, box: null, status: 'idle' };
}
