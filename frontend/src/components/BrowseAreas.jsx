import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';

function useRegions(level, parentId, enabled) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    if (!enabled) { setItems([]); return undefined; }
    const ac = new AbortController();
    api.regions(level, parentId, ac.signal).then(setItems).catch(() => setItems([]));
    return () => ac.abort();
  }, [level, parentId, enabled]);
  return items;
}

/** State -> district -> mandal -> village pick-lists. Choosing one drops the pin at that area's reference point. */
export default function BrowseAreas({ onPick }) {
  const { t, pick } = useI18n();
  const { meta } = useMeta();
  const [district, setDistrict] = useState('');
  const [mandal, setMandal] = useState('');
  const [village, setVillage] = useState('');
  const districts = useRegions('district', undefined, true);
  const mandals = useRegions('mandal', district || undefined, !!district);
  const villages = useRegions('village', mandal || undefined, !!mandal);

  const choose = (list, id) => {
    const it = list.find((x) => String(x.id) === String(id));
    if (it) onPick({ lat: it.lat, lon: it.lon, source: 'browse', label: it, inCoverage: it.in_coverage });
  };
  const sel = (id, label, value, list, onChange, disabled) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t('browse.choose')}</option>
        {list.map((x) => <option key={x.id} value={x.id}>{pick(x.name)}{x.in_coverage === false ? ` (${t('search.outside')})` : ''}</option>)}
      </select>
    </div>
  );

  return (
    <details className="browse">
      <summary>{t('browse.title')}</summary>
      <div className="browse__grid">
        <div className="field">
          <label htmlFor="b-state">{t('browse.state')}</label>
          <select id="b-state" value="TG" disabled><option value="TG">{pick(meta?.state?.name) || 'Telangana'}</option></select>
        </div>
        {sel('b-district', t('browse.district'), district, districts, (v) => { setDistrict(v); setMandal(''); setVillage(''); choose(districts, v); }, false)}
        {sel('b-mandal', t('browse.mandal'), mandal, mandals, (v) => { setMandal(v); setVillage(''); choose(mandals, v); }, !district)}
        {sel('b-village', t('browse.village'), village, villages, (v) => { setVillage(v); choose(villages, v); }, !mandal)}
      </div>
      <p className="browse__hint">{t('browse.hint')}</p>
    </details>
  );
}
