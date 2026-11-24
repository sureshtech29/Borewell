import { useI18n } from '../../i18n/index.jsx';
import DepthStrip from './DepthStrip.jsx';

function trendText(t, tr) {
  if (tr == null) return null;
  const m = Math.abs(tr), ft = (m * 3.28084).toFixed(1);
  if (m < 0.05) return t('water.trendStable');
  return t(tr > 0 ? 'water.trendFalling' : 'water.trendRising', { m: m.toFixed(2), ft });
}

export default function DepthSection({ a }) {
  const { t, pick, date } = useI18n();
  const w = a.water_table, d = a.drilling_depth;
  const water = w?.available ? w.pre_monsoon : null;
  const drill = d?.available ? d : null;
  const depthGap = a.data_gaps.find((g) => g.code === 'gap_depth_range');
  const waterGap = a.data_gaps.find((g) => g.code === 'gap_water_level');

  return (
    <section className="rsec" aria-labelledby="depth-h">
      <h3 id="depth-h">{t('depth.title')}</h3>
      <div className="depth-layout">
        <DepthStrip water={water} drill={drill} />
        <div className="depth-facts">
          <div className="fact">
            <h4>{t('depth.waterTitle')}</h4>
            {water ? (
              <>
                <p className="fact__big">{water.range_ft[0]}–{water.range_ft[1]} {t('unit.ft')} <span className="fact__sub">({water.range_m[0]}–{water.range_m[1]} {t('unit.m')})</span></p>
                <p className="fact__line">{t('water.pre', { est: water.estimate_ft })}</p>
                {w.post_monsoon && <p className="fact__line">{t('water.post', { lo: w.post_monsoon.range_ft[0], hi: w.post_monsoon.range_ft[1] })}</p>}
                <p className="fact__line">{t('water.basis', { n: w.n_wells, km: Math.round(w.radius_km), near: w.nearest_km })}</p>
                {trendText(t, w.trend_m_per_yr) && <p className="fact__line">{trendText(t, w.trend_m_per_yr)}</p>}
                {w.latest_reading_on && <p className="fact__line fact__line--muted">{t('water.latest', { date: date(w.latest_reading_on) })}</p>}
                <p className="fact__warn">{t('water.notDrilling')}</p>
              </>
            ) : (
              <p className="fact__none">{t('common.notAvailable')}{waterGap ? ` — ${pick(waterGap.text)}` : ''}</p>
            )}
          </div>
          <div className="fact">
            <h4>{t('depth.drillTitle')}</h4>
            {drill ? (
              <>
                <p className="fact__big">{drill.low_ft}–{drill.high_ft} {t('unit.ft')}</p>
                <p className="fact__line">{t('drill.basis', { n: drill.n_productive, km: Math.round(drill.radius_km) })}</p>
                {drill.n_dry > 0 && drill.dry_depth_max_ft != null && (
                  <p className="fact__line">{t('drill.dry', { n: drill.n_dry, ft: drill.dry_depth_max_ft })}</p>
                )}
                <p className="fact__warn">{t('drill.notPromise')}</p>
              </>
            ) : (
              <p className="fact__none">{t('common.notAvailable')}{depthGap ? ` — ${pick(depthGap.text)}` : ''}</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
