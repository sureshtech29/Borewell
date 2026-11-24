import { useI18n } from '../../i18n/index.jsx';
import { useMeta } from '../../hooks/useMeta.jsx';

const LEVELS = ['low', 'medium', 'high'];

export function ConfidenceMeter({ confidence }) {
  const { t, pick } = useI18n();
  const idx = Math.max(0, LEVELS.indexOf(confidence.level));
  return (
    <div className="conf">
      <div className="conf__row">
        <span className="conf__label">{t('conf.title')}</span>
        <strong className="conf__level">{pick(confidence.label)}</strong>
      </div>
      <div className="conf__bar" role="img" aria-label={`${t('conf.title')}: ${pick(confidence.label)}`}>
        {LEVELS.map((l, i) => <span key={l} className={i <= idx ? 'is-on' : ''} />)}
      </div>
      <p className="conf__what">{t('conf.what')}</p>
      {confidence.capped && <p className="conf__cap">{t('conf.capped')}</p>}
    </div>
  );
}

export default function Verdict({ a }) {
  const { t, pick } = useI18n();
  const { colorOf } = useMeta();
  const p = a.potential;
  const ok = a.status === 'ok';
  const label = pick(p.label);
  const heading = ok ? t('report.verdict', { label }) : pick(a.status_title) || label;
  return (
    <section className="verdict" style={{ '--cls': p.color || colorOf(p.class) }} aria-labelledby="verdict-h">
      <div className="verdict__swatch" aria-hidden="true" />
      <div className="verdict__body">
        <h2 id="verdict-h" className="verdict__title">{heading}</h2>
        {ok && p.score != null && <p className="verdict__score">{t('report.index', { score: Math.round(p.score) })}</p>}
        {p.insufficient_reason && <p className="verdict__why">{pick(p.insufficient_reason)}</p>}
      </div>
      {a.confidence && <ConfidenceMeter confidence={a.confidence} />}
      <p className="verdict__note">{pick(p.note)}</p>
    </section>
  );
}
