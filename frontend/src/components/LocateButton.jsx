import { useGeolocation } from '../hooks/useGeolocation.js';
import { useI18n } from '../i18n/index.jsx';

export default function LocateButton({ onLocated, variant = 'default' }) {
  const { t } = useI18n();
  const { startTracking, stopTracking, tracking, status, error } = useGeolocation();
  function toggle() {
    if (tracking) {
      stopTracking();
      return;
    }
    startTracking((p) => onLocated({ ...p, source: 'gps' }));
  }
  return (
    <div className="locate">
      <button type="button" className={`btn btn--gps${variant === 'big' ? ' btn--lg' : ''}`} onClick={toggle} aria-describedby={error ? 'gps-err' : undefined} aria-pressed={tracking}>
        <svg viewBox="0 0 24 24" aria-hidden="true" className="btn__icon"><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
        {tracking ? (status === 'locating' ? t('gps.locating') : t('gps.stop')) : t('gps.button')}
      </button>
      {tracking && <p className="site__help" role="status">{t('gps.live')}</p>}
      {error && <p id="gps-err" className="locate__err" role="alert">{t(`gps.err.${error}`)}</p>}
    </div>
  );
}
