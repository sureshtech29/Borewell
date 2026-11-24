import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, api } from '../api.js';
import { useI18n } from '../i18n/index.jsx';
import { formatLatLon } from '../utils/coords.js';
import Actions from './report/Actions.jsx';
import DepthSection from './report/DepthSection.jsx';
import EvidenceSection from './report/EvidenceSection.jsx';
import FactorsSection from './report/FactorsSection.jsx';
import { Gaps, Recommendations, Warnings } from './report/Lists.jsx';
import Sources from './report/Sources.jsx';
import Verdict from './report/Verdict.jsx';

function Place({ a }) {
  const { t, pick } = useI18n();
  const r = a.location.region;
  const chain = r ? [r.village, r.mandal, r.district, r.state].map(pick).filter(Boolean) : [];
  return (
    <header className="rp-head">
      {chain.length > 0 && <p className="rp-head__place">{chain.join(', ')}</p>}
      {r?.method === 'nearest_place' && r.nearest_place_km != null && (
        <p className="rp-head__hint">{t('place.nearest', { km: r.nearest_place_km })}</p>
      )}
      <p className="rp-head__coords">
        {formatLatLon(a.location.lat, a.location.lon)}
        {a.location.accuracy_m != null && <span> · {t('place.accuracy', { m: Math.round(a.location.accuracy_m) })}</span>}
      </p>
      {a.location.accuracy_m != null && a.location.accuracy_m > 100 && <p className="rp-head__hint">{t('place.weakGps')}</p>}
      {r?.gw_category && <p className="rp-head__hint">{t('place.gwCat', { cat: pick(r.gw_category.label) })}</p>}
    </header>
  );
}

function ErrorBox({ error, onRetry }) {
  const { t } = useI18n();
  const key = error instanceof ApiError
    ? (error.status === 0 ? 'err.network' : error.status === 429 ? 'err.rate' : error.status === 422 ? 'err.invalid' : 'err.server')
    : 'err.server';
  return (
    <div className="state state--error" role="alert">
      <p>{t(key)}</p>
      {key !== 'err.invalid' && <button type="button" className="btn" onClick={onRetry}>{t('common.retry')}</button>}
    </div>
  );
}

/** The analysis for one location. variant "panel" sits beside the map; "page" is the full report page. */
export default function ReportPanel({ point, analysis, variant = 'panel' }) {
  const { t, pick, dateTime, lang } = useI18n();
  const navigate = useNavigate();
  const [aiState, setAiState] = useState('idle');
  const [aiText, setAiText] = useState('');
  const [aiError, setAiError] = useState('');
  const { status, data: a, error, retry } = analysis;

  if (!point) return null;
  if ((status === 'loading' || status === 'idle') && !a) {
    return (
      <div className="state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>{t('report.loading')}</p>
      </div>
    );
  }
  if (status === 'error') return <ErrorBox error={error} onRetry={retry} />;
  if (!a) return null;

  const openFull = () => navigate(`/report?lat=${point.lat.toFixed(6)}&lon=${point.lon.toFixed(6)}${point.accuracy ? `&acc=${Math.round(point.accuracy)}` : ''}`);
  const ok = a.status === 'ok';
  const demo = a.warnings.find((w) => w.code === 'demo_data');
  const explain = async () => {
    setAiState('loading'); setAiError(''); setAiText('');
    try {
      const result = await api.explainWithAI(a, lang);
      if (result.status === 'not_configured') { setAiState('unconfigured'); setAiError(t('ai.notConfigured')); }
      else { setAiText(result.explanation); setAiState('done'); }
    } catch { setAiState('error'); setAiError(t('ai.error')); }
  };

  return (
    <article className={`report report--${variant}`} aria-busy={status === 'loading'}>
      {demo && <p className="report__demo" role="note">{pick(demo.text)}</p>}
      <Place a={a} />
      <Verdict a={a} />
      {ok && <DepthSection a={a} />}
      {ok && <EvidenceSection a={a} />}
      <Warnings a={{ ...a, warnings: a.warnings.filter((w) => w.code !== 'demo_data') }} />
      <Gaps a={a} hideDepthGaps={ok} />
      <Recommendations a={a} />
      {ok && <FactorsSection a={a} />}
      <Sources a={a} />
      <section className="ai-explainer" aria-live="polite">
        <h3>{t('ai.title')}</h3>
        <p>{t('ai.intro')}</p>
        <button type="button" className="btn btn--secondary" onClick={explain} disabled={aiState === 'loading'}>
          {aiState === 'loading' ? t('ai.loading') : t('ai.button')}
        </button>
        {aiError && <p className="ai-explainer__notice" role="status">{aiError}</p>}
        {aiText && <div className="ai-explainer__answer"><p>{aiText}</p></div>}
        {aiText && <p className="ai-explainer__notice">{t('ai.notice')}</p>}
      </section>
      <Actions point={point} showOpen={variant === 'panel'} onOpen={openFull} />
      <p className="report__disclaimer">{pick(a.disclaimer)}</p>
      <p className="report__stamp">{t('report.generated', { when: dateTime(a.generated_at) })}</p>
    </article>
  );
}
