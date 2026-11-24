import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

/** Fetch the analysis for a point (or nothing when point is null). Cancels the previous request. */
export function useAnalysis(point) {
  const [state, setState] = useState({ status: 'idle', data: null, error: null });
  const [nonce, setNonce] = useState(0);
  const acRef = useRef(null);
  const lat = point?.lat, lon = point?.lon, accuracy = point?.accuracy;

  useEffect(() => {
    acRef.current?.abort();
    if (lat == null || lon == null) { setState({ status: 'idle', data: null, error: null }); return undefined; }
    const ac = new AbortController();
    acRef.current = ac;
    setState((s) => ({ status: 'loading', data: s.data && s.data.location.lat === lat && s.data.location.lon === lon ? s.data : null, error: null }));
    api.analyze({ lat, lon, accuracy }, ac.signal)
      .then((data) => setState({ status: 'ready', data, error: null }))
      .catch((error) => { if (error.name !== 'AbortError') setState({ status: 'error', data: null, error }); });
    return () => ac.abort();
  }, [lat, lon, accuracy, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, retry };
}
