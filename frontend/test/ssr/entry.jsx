// Bundled by test/ssr.test.js. Renders real components to HTML strings with injected data (no network, no DOM).
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { I18nProvider } from '../../src/i18n/index.jsx';
import { MetaProvider } from '../../src/hooks/useMeta.jsx';
import ReportPanel from '../../src/components/ReportPanel.jsx';
import Header from '../../src/components/Header.jsx';
import Footer from '../../src/components/Footer.jsx';
import DemoBanner from '../../src/components/DemoBanner.jsx';
import Legend from '../../src/components/Legend.jsx';
import Home from '../../src/pages/Home.jsx';
import About from '../../src/pages/About.jsx';
import Contact from '../../src/pages/Contact.jsx';
import ReportPage from '../../src/pages/ReportPage.jsx';

function Shell({ lang, meta, url, children }) {
  return (
    <I18nProvider initial={lang}>
      <MetaProvider value={meta}>
        <MemoryRouter initialEntries={[url || '/']}>{children}</MemoryRouter>
      </MetaProvider>
    </I18nProvider>
  );
}

export function renderReport({ lang, meta, analysis, variant = 'panel' }) {
  const point = { lat: analysis.location.lat, lon: analysis.location.lon, accuracy: analysis.location.accuracy_m };
  const state = { status: 'ready', data: analysis, error: null, retry() {} };
  return renderToStaticMarkup(
    <Shell lang={lang} meta={meta}><ReportPanel point={point} analysis={state} variant={variant} /></Shell>,
  );
}

const PAGES = { header: Header, footer: Footer, banner: DemoBanner, legend: Legend, home: Home, about: About, contact: Contact, report: ReportPage };
export function renderPage({ lang, meta, page, url }) {
  const C = PAGES[page];
  return renderToStaticMarkup(<Shell lang={lang} meta={meta} url={url}><C /></Shell>);
}
