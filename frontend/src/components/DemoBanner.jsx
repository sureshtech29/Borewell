import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';

export default function DemoBanner() {
  const { isDemo } = useMeta();
  const { t } = useI18n();
  if (!isDemo) return null;
  return <p className="demo-banner" role="note"><strong>{t('demo.title')}</strong> {t('demo.text')}</p>;
}
