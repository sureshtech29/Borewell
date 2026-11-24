import { useEffect, useState } from 'react';
import { useI18n } from '../i18n/index.jsx';
import { formatLatLon, parseCoordinates } from '../utils/coords.js';

/** Shows the selected site's coordinates and lets the person type exact ones - the keyboard alternative to clicking the map. */
export default function SiteInput({ point, onPick, onClear }) {
  const { t } = useI18n();
  const [text, setText] = useState('');
  const [err, setErr] = useState(null);
  useEffect(() => { setText(point ? formatLatLon(point.lat, point.lon) : ''); setErr(null); }, [point?.lat, point?.lon]); // eslint-disable-line react-hooks/exhaustive-deps

  function submit(e) {
    e.preventDefault();
    const r = parseCoordinates(text);
    if (!r.ok) { setErr(r.error === 'range' ? 'search.coordRange' : 'search.coordFormat'); return; }
    setErr(null);
    onPick({ lat: r.lat, lon: r.lon, source: 'coords', swapped: r.swapped });
  }

  return (
    <form className="site" onSubmit={submit} noValidate>
      <label htmlFor="site-coords">{t('site.label')}</label>
      <div className="site__row">
        <input id="site-coords" type="text" inputMode="decimal" value={text} onChange={(e) => setText(e.target.value)} placeholder="17.38500, 78.48670"
          aria-invalid={!!err} aria-describedby={err ? 'site-err' : 'site-help'} />
        <button type="submit" className="btn">{t('site.go')}</button>
        {point && <button type="button" className="btn btn--quiet" onClick={onClear}>{t('site.clear')}</button>}
      </div>
      {err ? <p id="site-err" className="search__err" role="alert">{t(err)}</p> : <p id="site-help" className="site__help">{t('site.help')}</p>}
    </form>
  );
}
