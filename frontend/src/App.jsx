import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import DemoBanner from './components/DemoBanner.jsx';
import Footer from './components/Footer.jsx';
import Header from './components/Header.jsx';
import { useMeta } from './hooks/useMeta.jsx';
import { useI18n } from './i18n/index.jsx';
import About from './pages/About.jsx';
import Contact from './pages/Contact.jsx';
import Home from './pages/Home.jsx';
import MapPage from './pages/MapPage.jsx';
import ReportPage from './pages/ReportPage.jsx';

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { if (pathname !== '/map') window.scrollTo(0, 0); }, [pathname]);
  return null;
}

export default function App() {
  const { t } = useI18n();
  const { status, retry } = useMeta();
  const { pathname } = useLocation();
  const fullScreen = pathname === '/map';

  return (
    <div className={`app${fullScreen ? ' app--map' : ''}`}>
      <a className="skip" href="#main">{t('a11y.skip')}</a>
      <DemoBanner />
      <Header />
      <ScrollTop />
      {status === 'error' ? (
        <main id="main" className="page"><div className="state state--error" role="alert"><p>{t('err.noApi')}</p><button type="button" className="btn" onClick={retry}>{t('common.retry')}</button></div></main>
      ) : status === 'loading' ? (
        <main id="main" className="page"><div className="state" role="status"><span className="spinner" aria-hidden="true" /><p>{t('common.loading')}</p></div></main>
      ) : (
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
      {!fullScreen && <Footer />}
    </div>
  );
}
