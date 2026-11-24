import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.jsx';
import { formatLatLon, parseCoordinates } from '../utils/coords.js';

/**
 * One box for everything: village / mandal / district names (English or Telugu), a 6-digit PIN code,
 * or pasted coordinates. Coordinates are recognised locally; names go to /search after a short pause.
 * onPick({ lat, lon, source, label?, inCoverage? })
 */
export default function SearchBox({ onPick, autoFocus = false, large = false }) {
  const { t, pick } = useI18n();
  const uid = useId();
  const listId = `${uid}-list`;
  const [q, setQ] = useState('');
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState('idle');   // idle | loading | done | error
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const boxRef = useRef(null);

  const coords = useMemo(() => (/\d/.test(q) ? parseCoordinates(q) : null), [q]);
  const asCoords = coords?.ok ? coords : null;
  const coordError = coords && !coords.ok && /^[\s\d.,;°'"′″NSEWnsew/+-]+$/.test(q) && /\d[\s,;/]+[\d-]/.test(q) ? coords.error : null;

  useEffect(() => {
    const text = q.trim();
    if (text.length < 2 || asCoords) { setItems([]); setStatus('idle'); return undefined; }
    const ac = new AbortController();
    setStatus('loading');
    const timer = setTimeout(() => {
      api.search(text, ac.signal)
        .then((r) => { setItems(r); setStatus('done'); setActive(-1); })
        .catch((e) => { if (e.name !== 'AbortError') setStatus('error'); });
    }, 250);
    return () => { clearTimeout(timer); ac.abort(); };
  }, [q, asCoords]);

  useEffect(() => {
    const away = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, []);

  const options = asCoords
    ? [{ kind: 'coords', id: 'coords', coords: asCoords }]
    : items.map((it) => ({ kind: 'place', id: `${it.type}-${it.id}`, it }));

  function choose(opt) {
    if (!opt) return;
    setOpen(false);
    if (opt.kind === 'coords') {
      setQ(formatLatLon(opt.coords.lat, opt.coords.lon));
      onPick({ lat: opt.coords.lat, lon: opt.coords.lon, source: 'coords', swapped: opt.coords.swapped });
    } else {
      setQ(pick(opt.it.name));
      onPick({ lat: opt.it.lat, lon: opt.it.lon, source: 'search', label: opt.it, inCoverage: opt.it.in_coverage });
    }
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((i) => Math.min(options.length - 1, i + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(0, i - 1)); }
    else if (e.key === 'Escape') setOpen(false);
    else if (e.key === 'Enter') { e.preventDefault(); choose(options[active >= 0 ? active : 0]); }
  }

  const showList = open && (options.length > 0 || status === 'done' || status === 'error');
  return (
    <div className={`search${large ? ' search--lg' : ''}`} ref={boxRef}>
      <label className="search__label" htmlFor={`${uid}-in`}>{t('search.label')}</label>
      <div className="search__field">
        <input
          id={`${uid}-in`} type="search" value={q} autoFocus={autoFocus} autoComplete="off" autoCorrect="off" spellCheck="false" enterKeyHint="search"
          placeholder={t('search.placeholder')}
          role="combobox" aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${uid}-o${active}` : undefined}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(-1); }}
          onFocus={() => setOpen(true)} onKeyDown={onKey}
        />
        {status === 'loading' && <span className="spinner spinner--sm" aria-hidden="true" />}
      </div>
      {coordError && <p className="search__err" role="alert">{t(coordError === 'range' ? 'search.coordRange' : 'search.coordFormat')}</p>}
      <ul id={listId} role="listbox" className="search__list" hidden={!showList}>
        {options.map((o, i) => (
          <li key={o.id} id={`${uid}-o${i}`} role="option" aria-selected={i === active} className={i === active ? 'is-active' : ''}
            onPointerDown={(e) => { e.preventDefault(); choose(o); }}>
            {o.kind === 'coords' ? (
              <>
                <strong>{t('search.goTo', { coords: formatLatLon(o.coords.lat, o.coords.lon) })}</strong>
                {o.coords.swapped && <span className="search__sub">{t('search.swapped')}</span>}
              </>
            ) : (
              <>
                <span className="search__name"><strong>{pick(o.it.name)}</strong><em>{t(`search.type.${o.it.type}`)}</em></span>
                <span className="search__sub">{pick(o.it.context)}{o.it.pincode ? ` · ${o.it.pincode}` : ''}{o.it.in_coverage === false ? ` · ${t('search.outside')}` : ''}</span>
              </>
            )}
          </li>
        ))}
        {status === 'done' && options.length === 0 && <li className="search__none" role="presentation">{t('search.none')}</li>}
        {status === 'error' && <li className="search__none" role="presentation">{t('search.error')}</li>}
      </ul>
    </div>
  );
}
