import { useI18n } from '../../i18n/index.jsx';

function List({ id, title, items, tone }) {
  const { pick } = useI18n();
  if (!items?.length) return null;
  return (
    <section className={`rsec rsec--${tone}`} aria-labelledby={id}>
      <h3 id={id}>{title}</h3>
      <ul className="plain">{items.map((m) => <li key={m.code + pick(m.text)}>{pick(m.text)}</li>)}</ul>
    </section>
  );
}

export function Warnings({ a }) {
  const { t } = useI18n();
  return <List id="warn-h" tone="warn" title={t('lists.warnings')} items={a.warnings} />;
}
export function Gaps({ a, hideDepthGaps = false }) {
  const { t } = useI18n();
  // when the depth section is shown, its two gaps are written next to the numbers they explain
  const items = hideDepthGaps ? a.data_gaps.filter((g) => g.code !== 'gap_depth_range' && g.code !== 'gap_water_level') : a.data_gaps;
  return <List id="gaps-h" tone="gap" title={t('lists.gaps')} items={items} />;
}
export function Recommendations({ a }) {
  const { t } = useI18n();
  return <List id="rec-h" tone="rec" title={t('lists.recs')} items={a.recommendations} />;
}
