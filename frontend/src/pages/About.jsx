import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';

// [section, number of bullet points] - keys are about.<section>.<n> in the dictionaries
const LISTS = [['limits', 5], ['privacy', 4]];

export default function About() {
  const { t, pick, date } = useI18n();
  const { meta, isDemo } = useMeta();
  const [ds, setDs] = useState(null);
  useEffect(() => {
    const ac = new AbortController();
    api.datasets(ac.signal).then(setDs).catch(() => setDs({ error: true }));
    return () => ac.abort();
  }, []);
  const factors = meta?.method?.factors || [];

  return (
    <main id="main" className="page prose">
      <h1 className="page__title">{t('about.title')}</h1>
      <p className="prose__lead">{t('about.lead')}</p>
      {isDemo && <p className="callout callout--demo"><strong>{t('demo.title')}</strong> {t('about.demo')}</p>}

      <section aria-labelledby="ab-what">
        <h2 id="ab-what">{t('about.what.h')}</h2>
        <p>{t('about.what.p1')}</p>
        <p>{t('about.what.p2')}</p>
      </section>

      <section aria-labelledby="ab-method">
        <h2 id="ab-method">{t('about.method.h')}</h2>
        <p>{t('about.method.p')}</p>
        {factors.length > 0 && (
          <table className="tbl">
            <thead><tr><th scope="col">{t('factors.factor')}</th><th scope="col" className="num">{t('factors.weight')}</th></tr></thead>
            <tbody>{factors.map((f) => <tr key={f.key}><th scope="row">{pick(f.label)}</th><td className="num">{Math.round(f.weight * 100)}%</td></tr>)}</tbody>
          </table>
        )}
        <p>{t('about.method.p2')}</p>
        <p className="muted">{t('about.method.calib')}</p>
      </section>

      <section aria-labelledby="ab-conf">
        <h2 id="ab-conf">{t('about.conf.h')}</h2>
        <p>{t('about.conf.p1')}</p>
        <p>{t('about.conf.p2')}</p>
      </section>

      <section aria-labelledby="ab-data">
        <h2 id="ab-data">{t('about.data.h')}</h2>
        <p>{t('about.data.p')}</p>
        {!ds && <p className="muted">{t('common.loading')}</p>}
        {ds?.error && <p className="muted">{t('err.server')}</p>}
        {ds?.sources && (
          <ul className="sources">
            {ds.sources.map((s) => (
              <li key={s.id}>
                <strong>{pick(s.name)}</strong>
                <span>{s.publisher}</span>
                <span className="muted">{t('sources.updated', { date: s.data_last_updated ? date(s.data_last_updated) : t('common.notAvailable') })}{s.license ? ` · ${s.license}` : ''}</span>
                {s.notes && <span className="muted">{s.notes}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {LISTS.map(([b, n]) => (
        <section key={b} aria-labelledby={`ab-${b}`}>
          <h2 id={`ab-${b}`}>{t(`about.${b}.h`)}</h2>
          <ul className="plain">
            {Array.from({ length: n }, (_, i) => <li key={i}>{t(`about.${b}.${i + 1}`)}</li>)}
          </ul>
        </section>
      ))}

      <p><Link className="btn btn--primary" to="/map">{t('home.openMap')}</Link> <Link className="btn" to="/contact">{t('nav.contact')}</Link></p>
    </main>
  );
}
