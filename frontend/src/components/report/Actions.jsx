import { useState } from 'react';
import { reportUrl } from '../../api.js';
import { useI18n } from '../../i18n/index.jsx';

/** PDF download with a graceful fallback: if the server cannot make PDFs (501), open the printable page instead. */
export default function Actions({ point, showOpen = true, onOpen }) {
  const { t, lang } = useI18n();
  const [state, setState] = useState({ busy: false, msg: null });

  async function download() {
    setState({ busy: true, msg: null });
    try {
      const res = await fetch(reportUrl('pdf', point, lang), { referrerPolicy: 'no-referrer' });
      if (res.status === 501) {
        window.open(reportUrl('html', point, lang), '_blank', 'noopener');
        setState({ busy: false, msg: 'fallback' });
        return;
      }
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `borewell-report_${point.lat.toFixed(4)}_${point.lon.toFixed(4)}_${lang}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setState({ busy: false, msg: null });
    } catch {
      setState({ busy: false, msg: 'error' });
    }
  }

  async function copyLink() {
    const u = new URL('/map', window.location.origin);
    u.searchParams.set('lat', point.lat.toFixed(6));
    u.searchParams.set('lon', point.lon.toFixed(6));
    try { await navigator.clipboard.writeText(u.toString()); setState({ busy: false, msg: 'copied' }); } catch { setState({ busy: false, msg: 'copyfail' }); }
  }

  return (
    <div className="actions">
      <div className="actions__row">
        <button type="button" className="btn btn--primary" onClick={download} disabled={state.busy}>{state.busy ? t('actions.preparing') : t('actions.pdf')}</button>
        <a className="btn" href={reportUrl('html', point, lang)} target="_blank" rel="noopener">{t('actions.print')}</a>
        <button type="button" className="btn" onClick={copyLink}>{t('actions.copy')}</button>
        {showOpen && <button type="button" className="btn" onClick={onOpen}>{t('actions.fullReport')}</button>}
      </div>
      <p className="actions__msg" role="status" aria-live="polite">
        {state.msg === 'fallback' && t('actions.pdfFallback')}
        {state.msg === 'error' && t('actions.pdfError')}
        {state.msg === 'copied' && t('actions.copied')}
        {state.msg === 'copyfail' && t('actions.copyFail')}
      </p>
    </div>
  );
}
