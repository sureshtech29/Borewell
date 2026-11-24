import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import BrowseAreas from '../components/BrowseAreas.jsx';
import LocateButton from '../components/LocateButton.jsx';
import MapView from '../components/MapView.jsx';
import ReportPanel from '../components/ReportPanel.jsx';
import SearchBox from '../components/SearchBox.jsx';
import SiteInput from '../components/SiteInput.jsx';
import { api } from '../api.js';
import { useAnalysis } from '../hooks/useAnalysis.js';
import { useI18n } from '../i18n/index.jsx';
import { pointFromParams, pointSearch } from '../utils/point.js';

export default function MapPage() {
  const { t, pick } = useI18n();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const source = location.state?.source;
  const point = useMemo(() => pointFromParams(params, source), [params, source]);
  const analysis = useAnalysis(point);
  const [focus, setFocus] = useState(null);
  const [note, setNote] = useState(null);
  const [sheet, setSheet] = useState('open');          // phones: 'open' | 'peek'
  const resultRef = useRef(null);
  const [drawing, setDrawing] = useState(false);
  const [boundary, setBoundary] = useState([]);
  const [ranking, setRanking] = useState(null);
  const [rankingBusy, setRankingBusy] = useState(false);
  const [rankingError, setRankingError] = useState(null);

  // phones: the search form sits above the result inside the bottom sheet, so bring the result into view when a site is chosen
  const lat = point?.lat, lon = point?.lon;
  useEffect(() => {
    if (lat == null || typeof window === 'undefined' || !window.matchMedia('(max-width: 859px)').matches) return;
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    resultRef.current?.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' });
  }, [lat, lon]);

  // arriving from a shared link / the home page: fly to the site once
  useEffect(() => {
    if (point && !focus) setFocus({ lat: point.lat, lon: point.lon, zoom: source === 'gps' ? 15 : 14, nonce: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const select = useCallback((p) => {
    navigate({ pathname: '/map', search: pointSearch(p) }, { state: { source: p.source } });
    if (p.source !== 'map' && p.source !== 'drag') {
      const zoom = p.source === 'gps' ? (p.accuracy < 200 ? 15 : 13) : p.source === 'browse' ? 12 : 14;
      setFocus({ lat: p.lat, lon: p.lon, zoom, nonce: Date.now() });
    }
    setNote(p.swapped ? 'swapped' : p.source === 'browse' ? 'browse' : p.inCoverage === false ? 'outside' : null);
    setSheet('open');
  }, [navigate]);

  const clear = useCallback(() => { setNote(null); navigate('/map'); }, [navigate]);

  return (
    <main id="main" className="mappage" data-sheet={sheet}>
      <MapView point={point} onSelect={select} focus={focus} drawing={drawing} boundary={boundary} candidates={ranking?.candidates || []} onBoundaryPoint={(p) => { setBoundary((old) => old.length < 20 ? [...old, p] : old); setRanking(null); }} />
      <aside className="panel" aria-label={t('map.panel')}>
        <button type="button" className="panel__handle" aria-expanded={sheet === 'open'} onClick={() => setSheet(sheet === 'open' ? 'peek' : 'open')}>
          <span aria-hidden="true" className="panel__grip" />
          {sheet === 'open' ? t('map.hidePanel') : t('map.showPanel')}
        </button>
        <div className="panel__top">
          <h1 className="panel__title">{t('map.title')}</h1>
          <SearchBox onPick={select} />
          <LocateButton onLocated={select} />
          <BrowseAreas onPick={select} />
          <SiteInput point={point} onPick={select} onClear={clear} />
          <section className="plot-tool" aria-label="Plot site ranking">
            <h2>{t('plot.title')}</h2>
            <p>{t('plot.intro')}</p>
            <div className="site__row">
              <button type="button" className="btn" onClick={() => { setDrawing((v) => !v); setRanking(null); }}>{drawing ? t('plot.stop') : t('plot.draw')}</button>
              <button type="button" className="btn btn--quiet" onClick={() => { setBoundary([]); setRanking(null); setRankingError(null); }}>{t('plot.clear')}</button>
            </div>
            <p className="site__help">{t('plot.points', { n: boundary.length })} {drawing ? t('plot.tap') : t('plot.edit')}</p>
            <button type="button" className="btn btn--primary" disabled={boundary.length < 3 || rankingBusy} onClick={async () => {
              setRankingBusy(true); setRankingError(null); setRanking(null); setDrawing(false);
              try { setRanking(await api.rankPlot(boundary)); } catch (e) { setRankingError(e.message || 'Could not rank this plot.'); } finally { setRankingBusy(false); }
            }}>{rankingBusy ? t('plot.analysing') : t('plot.rank')}</button>
            {rankingError && <p className="search__err" role="alert">{rankingError}</p>}
            {ranking && <div className="plot-results" aria-live="polite">
              <strong>{t('plot.count', { n: ranking.candidate_count })}</strong>
              {ranking.is_demo && <p className="plot-results__warning">{t('plot.demo')}</p>}
              <ol>{ranking.candidates.map((item) => <li key={item.id}><strong>#{item.rank} · {pick(item.potential_label) || item.potential_class}</strong> — {item.score == null ? t('plot.noScore') : `${item.score.toFixed(1)}/100`} · {item.confidence_level} {t('plot.confidence')}<br /><small>{item.lat.toFixed(5)}, {item.lon.toFixed(5)}</small></li>)}</ol>
              <p className="site__help">{t('plot.caution')}</p>
            </div>}
          </section>
          {note && <p className="panel__note" role="status">{t(`map.note.${note}`)}</p>}
        </div>
        <div className="panel__scroll" ref={resultRef}>
          {!point && <p className="panel__empty">{t('map.empty')}</p>}
          <ReportPanel point={point} analysis={analysis} />
        </div>
      </aside>
    </main>
  );
}
