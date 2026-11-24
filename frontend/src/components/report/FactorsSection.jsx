import { useI18n } from '../../i18n/index.jsx';

export default function FactorsSection({ a }) {
  const { t, pick } = useI18n();
  if (!a.factors?.length) return null;
  return (
    <details className="rsec rsec--details">
      <summary><h3>{t('factors.title')}</h3></summary>
      <p className="rsec__lead">{t('factors.lead')}</p>
      <table className="tbl">
        <thead>
          <tr><th scope="col">{t('factors.factor')}</th><th scope="col">{t('factors.value')}</th><th scope="col" className="num">{t('factors.score')}</th><th scope="col" className="num">{t('factors.weight')}</th></tr>
        </thead>
        <tbody>
          {a.factors.map((f) => (
            <tr key={f.key}>
              <th scope="row">{pick(f.label)}</th>
              <td>
                {!f.applicable ? <span className="muted">{t('common.notApplicable')}</span>
                  : !f.available ? <span className="muted">{t('common.noData')}</span>
                  : pick(f.display)}
              </td>
              <td className="num">
                {f.score != null ? (
                  <span className="scorebar" title={`${Math.round(f.score)} / 100`}>
                    <i style={{ width: `${Math.max(2, Math.min(100, f.score))}%` }} />
                    <b>{Math.round(f.score)}</b>
                  </span>
                ) : '–'}
              </td>
              <td className="num">{f.applicable && f.available ? `${Math.round(f.effective_weight * 100)}%` : '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {a.rainfall && (
        <p className="rsec__foot">
          {t('factors.rain', { y0: a.rainfall.years[0], y1: a.rainfall.years[1], mean: Math.round(a.rainfall.recent_mean_mm) })}
          {a.rainfall.normal_mm ? ` ${t('factors.rainNormal', { normal: Math.round(a.rainfall.normal_mm), pct: `${a.rainfall.anomaly_pct > 0 ? '+' : ''}${Math.round(a.rainfall.anomaly_pct)}` })}` : ''}
        </p>
      )}
      {a.confidence?.components && (
        <>
          <h4 className="rsec__sub">{t('conf.how')}</h4>
          <ul className="complist">
            {a.confidence.components.map((c) => (
              <li key={c.key}>
                <span>{pick(c.label)}</span>
                <span className="scorebar"><i style={{ width: `${Math.max(2, c.value * 100)}%` }} /><b>{Math.round(c.value * 100)}%</b></span>
              </li>
            ))}
          </ul>
          <p className="rsec__foot">{pick(a.confidence.note)}</p>
        </>
      )}
    </details>
  );
}
