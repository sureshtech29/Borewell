import { useCallback, useEffect, useRef, useState } from 'react';

/** User-controlled live GPS tracking. Location is shared only after the user presses the button. */
export function useGeolocation() {
  const [state, setState] = useState({ status: 'idle', error: null });
  const watchId = useRef(null);
  const lastFix = useRef(null);

  const stopTracking = useCallback(() => {
    if (watchId.current !== null && typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchId.current);
    }
    watchId.current = null;
    lastFix.current = null;
    setState((old) => ({ status: old.status === 'error' ? 'error' : 'idle', error: old.error }));
  }, []);

  const startTracking = useCallback((onUpdate) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setState({ status: 'error', error: 'unsupported' });
      return;
    }
    if (watchId.current !== null) return;
    setState({ status: 'locating', error: null });
    watchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        setState({ status: 'tracking', error: null });
        const next = { lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy, timestamp: pos.timestamp };
        // Ignore tiny GPS jitter so the app does not rerun groundwater analysis unnecessarily.
        const previous = lastFix.current;
        const rad = (v) => (v * Math.PI) / 180;
        const distance = previous ? 6371000 * 2 * Math.asin(Math.sqrt(
          Math.sin(rad(next.lat - previous.lat) / 2) ** 2 +
          Math.cos(rad(previous.lat)) * Math.cos(rad(next.lat)) * Math.sin(rad(next.lon - previous.lon) / 2) ** 2
        )) : Infinity;
        if (distance >= 20 || !previous) { lastFix.current = next; onUpdate(next); }
      },
      (err) => {
        const code = err.code === 1 ? 'denied' : err.code === 3 ? 'timeout' : 'unavailable';
        setState({ status: 'error', error: code });
        if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
        watchId.current = null;
        lastFix.current = null;
      },
      { enableHighAccuracy: true, timeout: 30000, maximumAge: 2000 },
    );
  }, []);

  useEffect(() => () => {
    if (watchId.current !== null && typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchId.current);
    }
  }, []);

  return { ...state, startTracking, stopTracking, tracking: state.status === 'tracking' || state.status === 'locating' };
}
