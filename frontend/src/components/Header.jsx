import { Link, NavLink } from 'react-router-dom';
import { useI18n } from '../i18n/index.jsx';

export function Logo() {
  return (
    <svg className="logo" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#2B1B57" />
      <path d="M16 5v15" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
      <path d="M7 24q4.5-3.4 9 0t9 0" fill="none" stroke="#B9A6F2" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

export default function Header() {
  const { t, lang, setLang } = useI18n();
  const other = lang === 'en' ? 'te' : 'en';
  return (
    <header className="site-header">
      <Link to="/" className="brand" aria-label={t('nav.home')}>
        <Logo />
        <span className="brand__name">{t('app.name')}</span>
      </Link>
      <nav className="site-nav" aria-label={t('nav.label')}>
        <NavLink to="/" end>{t('nav.home')}</NavLink>
        <NavLink to="/map">{t('nav.map')}</NavLink>
        <NavLink to="/about">{t('nav.about')}</NavLink>
        <NavLink to="/contact">{t('nav.contact')}</NavLink>
      </nav>
      <button type="button" className="lang" onClick={() => setLang(other)} lang={other} aria-label={t('lang.switchTo')}>
        {other === 'te' ? 'తెలుగు' : 'English'}
      </button>
    </header>
  );
}
