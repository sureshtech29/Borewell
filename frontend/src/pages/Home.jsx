import { Link, useNavigate } from 'react-router-dom';
import LocateButton from '../components/LocateButton.jsx';
import Legend from '../components/Legend.jsx';
import SearchBox from '../components/SearchBox.jsx';
import Strata from '../components/Strata.jsx';
import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';
import { pointSearch } from '../utils/point.js';

const SOURCES = ['cgwb', 'wris', 'gsi', 'tgwd', 'imd'];

export default function Home() {
  const { t } = useI18n();
  const { isDemo } = useMeta();
  const navigate = useNavigate();
  const go = (p) => navigate({ pathname: '/map', search: pointSearch(p) }, { state: { source: p.source } });

  return (
    <main id="main" className="home">
      <section className="hero" aria-labelledby="hero-h">
        <div className="hero__text">
          <h1 id="hero-h">{t('home.h1')}</h1>
          <p className="hero__lead">{t('home.lead')}</p>
          <div className="hero__find">
            <SearchBox onPick={go} large />
            <div className="hero__or"><span>{t('home.or')}</span></div>
            <div className="hero__actions">
              <LocateButton onLocated={go} variant="big" />
              <Link to="/map" className="btn btn--lg">{t('home.openMap')}</Link>
            </div>
          </div>
          <p className="hero__fine">{t('home.fine')}</p>
        </div>
        <Strata />
      </section>

      <section className="band" aria-labelledby="colours-h">
        <div className="band__in">
          <div className="band__head">
            <h2 id="colours-h">{t('home.coloursH')}</h2>
            <p>{t('home.coloursP')}</p>
          </div>
          <Legend />
        </div>
      </section>

      <section className="band band--plain" aria-labelledby="limits-h">
        <div className="band__in band__in--two">
          <div>
            <h2 id="limits-h">{t('home.tellsH')}</h2>
            <ul className="plain plain--tick">
              {['t1', 't2', 't3', 't4'].map((k) => <li key={k}>{t(`home.tells.${k}`)}</li>)}
            </ul>
          </div>
          <div>
            <h2>{t('home.onlyH')}</h2>
            <ul className="plain plain--cross">
              {['o1', 'o2', 'o3', 'o4'].map((k) => <li key={k}>{t(`home.only.${k}`)}</li>)}
            </ul>
          </div>
        </div>
      </section>

      <section className="band" aria-labelledby="src-h">
        <div className="band__in">
          <div className="band__head">
            <h2 id="src-h">{t('home.srcH')}</h2>
            <p>{isDemo ? t('home.srcDemo') : t('home.srcLive')}</p>
          </div>
          <ul className="srclist">
            {SOURCES.map((s) => (
              <li key={s}><strong>{t(`home.src.${s}.n`)}</strong><span>{t(`home.src.${s}.d`)}</span></li>
            ))}
          </ul>
          <p><Link to="/about">{t('home.srcMore')}</Link></p>
        </div>
      </section>
    </main>
  );
}
