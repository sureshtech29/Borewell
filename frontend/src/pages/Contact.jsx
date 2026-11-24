import { useState } from 'react';
import { ApiError, api } from '../api.js';
import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';

export default function Contact() {
  const { t, lang } = useI18n();
  const { meta } = useMeta();
  const [form, setForm] = useState({ name: '', email: '', phone: '', message: '' });
  const [state, setState] = useState({ status: 'idle', error: null });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (!form.email.trim() && !form.phone.trim()) { setState({ status: 'error', error: 'need' }); return; }
    setState({ status: 'sending', error: null });
    try {
      await api.contact({ name: form.name.trim(), email: form.email.trim() || null, phone: form.phone.trim() || null, message: form.message.trim(), lang });
      setState({ status: 'sent', error: null });
      setForm({ name: '', email: '', phone: '', message: '' });
    } catch (err) {
      setState({ status: 'error', error: err instanceof ApiError ? (err.status === 429 ? 'rate' : err.status === 422 ? 'invalid' : err.status === 0 ? 'network' : 'server') : 'server' });
    }
  }

  return (
    <main id="main" className="page prose">
      <h1 className="page__title">{t('contact.title')}</h1>
      <p className="prose__lead">{t('contact.lead')}</p>
      {meta?.contact_email && <p>{t('contact.email')} <a href={`mailto:${meta.contact_email}`}>{meta.contact_email}</a></p>}
      {state.status === 'sent' ? (
        <p className="callout" role="status">{t('contact.sent')}</p>
      ) : (
        <form className="form" onSubmit={submit} noValidate>
          <div className="field"><label htmlFor="c-name">{t('contact.name')}</label>
            <input id="c-name" required maxLength={120} value={form.name} onChange={set('name')} autoComplete="name" /></div>
          <div className="field"><label htmlFor="c-email">{t('contact.emailField')}</label>
            <input id="c-email" type="email" maxLength={200} value={form.email} onChange={set('email')} autoComplete="email" /></div>
          <div className="field"><label htmlFor="c-phone">{t('contact.phone')}</label>
            <input id="c-phone" type="tel" maxLength={30} value={form.phone} onChange={set('phone')} autoComplete="tel" /></div>
          <p className="muted">{t('contact.either')}</p>
          <div className="field"><label htmlFor="c-msg">{t('contact.message')}</label>
            <textarea id="c-msg" required minLength={5} maxLength={4000} rows={6} value={form.message} onChange={set('message')} /></div>
          {state.status === 'error' && <p className="search__err" role="alert">{t(`contact.err.${state.error}`)}</p>}
          <p className="muted">{t('contact.privacy')}</p>
          <button type="submit" className="btn btn--primary" disabled={state.status === 'sending' || !form.name.trim() || form.message.trim().length < 5}>
            {state.status === 'sending' ? t('contact.sending') : t('contact.send')}
          </button>
        </form>
      )}
    </main>
  );
}
