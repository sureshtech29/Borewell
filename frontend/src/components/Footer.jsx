import { Link } from 'react-router-dom';
import { useI18n } from '../i18n/index.jsx';

export default function Footer() {
  const { t } = useI18n();
  return (
    <footer className="site-footer">
      <p className="site-footer__warn">{t('footer.disclaimer')}</p>
      <p className="site-footer__links">
        <Link to="/about">{t('nav.about')}</Link>
        <Link to="/contact">{t('nav.contact')}</Link>
      </p>
    </footer>
  );
}
