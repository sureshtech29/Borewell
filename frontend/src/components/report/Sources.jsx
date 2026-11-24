import { useI18n } from '../../i18n/index.jsx';

export default function Sources({ a }) {
  const { t, pick, date } = useI18n();
  return (
    <details className="rsec rsec--details">
      <summary><h3>{t('sources.title')}</h3></summary>
      {a.sources.length === 0 ? <p className="muted">{t('common.notAvailable')}</p> : (
        <ul className="sources">
          {a.sources.map((s) => (
            <li key={s.id}>
              <strong>{pick(s.name)}</strong>
              <span>{s.publisher}</span>
              <span className="muted">{t('sources.updated', { date: s.data_last_updated ? date(s.data_last_updated) : t('common.notAvailable') })}{s.license ? ` · ${s.license}` : ''}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="rsec__foot">{t('sources.method', { name: pick(a.method.name), version: a.method.version })}</p>
      {a.data_last_updated && <p className="rsec__foot">{t('sources.newest', { date: date(a.data_last_updated) })}</p>}
    </details>
  );
}
