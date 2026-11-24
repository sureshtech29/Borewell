import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import en from './en.js';
import te from './te.js';
import { fmtDate, fmtDateTime } from '../utils/format.js';

const DICT = { en, te };
const STORE_KEY = 'bwf.lang';

function initialLang() {
  try {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved === 'en' || saved === 'te') return saved;
  } catch { /* storage unavailable */ }
  const nav = typeof navigator !== 'undefined' ? (navigator.language || '') : '';
  return nav.toLowerCase().startsWith('te') ? 'te' : 'en';
}

const Ctx = createContext(null);

export function I18nProvider({ children, initial }) {
  const [lang, setLangState] = useState(initial || initialLang);
  const setLang = useCallback((l) => {
    setLangState(l);
    try { localStorage.setItem(STORE_KEY, l); } catch { /* ignore */ }
  }, []);
  useEffect(() => { if (typeof document !== 'undefined') document.documentElement.lang = lang; }, [lang]);

  const value = useMemo(() => {
    const t = (key, params) => {
      let s = DICT[lang][key] ?? DICT.en[key] ?? key;
      if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] !== undefined ? String(params[k]) : m));
      return s;
    };
    // API text arrives as { en, te }; fall back to English if a translation is missing.
    const pick = (obj) => (obj && typeof obj === 'object' ? (obj[lang] || obj.en || '') : (obj ?? ''));
    return { lang, setLang, t, pick, date: (d) => fmtDate(d, lang), dateTime: (d) => fmtDateTime(d, lang) };
  }, [lang, setLang]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useI18n must be used inside <I18nProvider>');
  return v;
}
