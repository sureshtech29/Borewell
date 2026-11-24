import { useState } from 'react';
import { useMeta } from '../hooks/useMeta.jsx';
import { useI18n } from '../i18n/index.jsx';

/** The five map classes. Full: colour + name + what it means. Compact: a collapsible key over the map. */
export default function Legend({ compact = false }) {
  const { t, pick } = useI18n();
  const { legend } = useMeta();
  // over a small map the key starts collapsed so it does not hide the map; it is open on larger screens
  const [open, setOpen] = useState(() => typeof window === 'undefined' || !window.matchMedia('(max-width: 859px)').matches);
  if (compact) {
    return (
      <details className="legend legend--compact" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary>{t('legend.title')}</summary>
        <ul>
          {legend.map((l) => (
            <li key={l.key}><span className="legend__sw" style={{ background: l.color }} aria-hidden="true" />{pick(l.label)}</li>
          ))}
        </ul>
      </details>
    );
  }
  return (
    <ul className="legend legend--full">
      {legend.map((l) => (
        <li key={l.key}>
          <span className="legend__sw legend__sw--lg" style={{ background: l.color }} aria-hidden="true" />
          <div>
            <strong>{pick(l.label)}</strong>
            <p>{t(`legend.${l.key}`)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
