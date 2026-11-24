import { useI18n } from '../../i18n/index.jsx';

export default function EvidenceSection({ a }) {
  const { t, pick } = useI18n();
  const ev = a.local_evidence;
  if (!ev) return null;
  const total = ev.outcomes.reduce((s, o) => s + o.count, 0);
  return (
    <section className="rsec" aria-labelledby="ev-h">
      <h3 id="ev-h">{t('evidence.title')}</h3>
      <p className="rsec__lead">
        {ev.n_records > 0
          ? t('evidence.count', { n: ev.n_records, km: Math.round(ev.radius_km) }) + (ev.nearest_record_km != null ? ' ' + t('evidence.nearest', { km: ev.nearest_record_km }) : '')
          : t('evidence.none', { km: Math.round(ev.radius_km) })}
      </p>
      {total > 0 && (
        <>
          <div className="outcomes" role="img" aria-label={ev.outcomes.map((o) => `${pick(o.label)}: ${o.count}`).join(', ')}>
            {ev.outcomes.filter((o) => o.count > 0).map((o) => (
              <span key={o.key} className={`outcomes__seg outcomes__seg--${o.key}`} style={{ flexGrow: o.count }} />
            ))}
          </div>
          <ul className="outcomes__legend">
            {ev.outcomes.map((o) => (
              <li key={o.key}><span className={`outcomes__dot outcomes__dot--${o.key}`} aria-hidden="true" />{pick(o.label)} <b>{o.count}</b></li>
            ))}
          </ul>
        </>
      )}
      <p className="rsec__foot">{ev.used ? t('evidence.used') : t('evidence.notUsed')}</p>
      {ev.ves?.length > 0 && (
        <>
          <h4 className="rsec__sub">{t('evidence.ves')}</h4>
          <ul className="plain">
            {ev.ves.map((v, i) => (
              <li key={i}>{t('evidence.vesItem', { km: v.distance_km, method: v.method, result: pick(v.suitability_label) })}{v.survey_year ? ` (${v.survey_year})` : ''}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
