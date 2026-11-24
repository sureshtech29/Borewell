import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import ReportPanel from '../components/ReportPanel.jsx';
import { useAnalysis } from '../hooks/useAnalysis.js';
import { useI18n } from '../i18n/index.jsx';
import { pointFromParams, pointSearch } from '../utils/point.js';

export default function ReportPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const point = useMemo(() => pointFromParams(params), [params]);
  const analysis = useAnalysis(point);
  return (
    <main id="main" className="page page--report">
      <p className="page__back">
        <Link to={point ? `/map?${pointSearch(point)}` : '/map'}>{t('report.back')}</Link>
      </p>
      <h1 className="page__title">{t('report.title')}</h1>
      {point ? <ReportPanel point={point} analysis={analysis} variant="page" /> : (
        <p className="state">{t('report.noPoint')} <Link to="/map">{t('home.openMap')}</Link></p>
      )}
    </main>
  );
}
