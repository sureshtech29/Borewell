import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import { FALLBACK_LEGEND } from '../config.js';

const Ctx = createContext(null);

export function MetaProvider({ children, value: injected }) {
  const [state, setState] = useState(injected ? { status: 'ready', meta: injected } : { status: 'loading', meta: null });

  const load = useCallback(() => {
    const ac = new AbortController();
    setState({ status: 'loading', meta: null });
    api.meta(ac.signal)
      .then((meta) => setState({ status: 'ready', meta }))
      .catch((e) => { if (e.name !== 'AbortError') setState({ status: 'error', meta: null, error: e }); });
    return () => ac.abort();
  }, []);

  useEffect(() => (injected ? undefined : load()), [injected, load]);

  const value = useMemo(() => {
    const legend = state.meta?.legend || FALLBACK_LEGEND.map((l) => ({ ...l, label: { en: l.key, te: l.key } }));
    const colors = Object.fromEntries(legend.map((l) => [l.key, l.color]));
    return { ...state, legend, colorOf: (k) => colors[k] || '#9AA3AD', retry: load, isDemo: state.meta?.data_mode === 'demo' };
  }, [state, load]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMeta() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useMeta must be used inside <MetaProvider>');
  return v;
}
