import { useI18n } from '../../i18n/index.jsx';
import { niceMax } from '../../utils/format.js';

const W = 300, H = 250, TOP = 18, BOTTOM = 232, AXIS_X = 46;
const COLS = { water: [70, 150], drill: [186, 266] };

/**
 * Depth chart in feet. Two columns on one scale:
 *  - hatched: depth to the water table (pre-monsoon) measured in nearby monitoring wells
 *  - solid: depths actually drilled in nearby borewells that gave water
 * They answer different questions: the water table is where water stands, the drilled depth is how far people had to go.
 * Neutral violet on purpose: the potential-class colours (blue/green/yellow/red) must keep one meaning on this site.
 */
export default function DepthStrip({ water, drill }) {
  const { t } = useI18n();
  const max = niceMax(Math.max(water?.range_ft?.[1] ?? 0, drill?.high_ft ?? 0));
  const y = (ft) => TOP + (ft / max) * (BOTTOM - TOP);
  const step = max <= 200 ? 50 : 100;
  const ticks = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);

  const summary = [
    water ? t('depth.aria.water', { lo: water.range_ft[0], hi: water.range_ft[1] }) : t('depth.aria.noWater'),
    drill ? t('depth.aria.drill', { lo: drill.low_ft, hi: drill.high_ft }) : t('depth.aria.noDrill'),
  ].join(' ');

  return (
    <figure className="depth">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} className="depth__svg">
        <defs>
          <pattern id="bwf-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="#EFEAFB" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#6A4FC4" strokeWidth="2" />
          </pattern>
        </defs>
        {/* ground surface */}
        <rect x={AXIS_X} y={TOP - 7} width={W - AXIS_X - 10} height="7" fill="#C9CFD3" />
        {ticks.map((v) => (
          <g key={v}>
            <line x1={AXIS_X} x2={W - 10} y1={y(v)} y2={y(v)} stroke="#DDE3E6" strokeWidth="1" />
            <text x={AXIS_X - 6} y={y(v) + 4} textAnchor="end" className="depth__tick">{v}</text>
          </g>
        ))}
        <text x={AXIS_X - 6} y="9" textAnchor="end" className="depth__unit">{t('unit.ft')}</text>

        {water ? (
          <g>
            <rect x={COLS.water[0]} y={y(water.range_ft[0])} width={COLS.water[1] - COLS.water[0]}
              height={Math.max(3, y(water.range_ft[1]) - y(water.range_ft[0]))} fill="url(#bwf-hatch)" stroke="#6A4FC4" strokeWidth="1.5" />
            {water.estimate_ft != null && (
              <line x1={COLS.water[0] - 4} x2={COLS.water[1] + 4} y1={y(water.estimate_ft)} y2={y(water.estimate_ft)} stroke="#2B1B57" strokeWidth="2.5" />
            )}
          </g>
        ) : (
          <g>
            <rect x={COLS.water[0]} y={y(0)} width={COLS.water[1] - COLS.water[0]} height="70" fill="none" stroke="#8A959E" strokeDasharray="4 4" />
            <text x={(COLS.water[0] + COLS.water[1]) / 2} y={y(0) + 38} textAnchor="middle" className="depth__none">{t('depth.noData')}</text>
          </g>
        )}

        {drill ? (
          <g>
            <rect x={COLS.drill[0]} y={y(drill.low_ft)} width={COLS.drill[1] - COLS.drill[0]}
              height={Math.max(4, y(drill.high_ft) - y(drill.low_ft))} fill="#4A2C82" />
            {drill.median_ft != null && (
              <line x1={COLS.drill[0]} x2={COLS.drill[1]} y1={y(drill.median_ft)} y2={y(drill.median_ft)} stroke="#fff" strokeWidth="2" />
            )}
          </g>
        ) : (
          <g>
            <rect x={COLS.drill[0]} y={y(0)} width={COLS.drill[1] - COLS.drill[0]} height="70" fill="none" stroke="#8A959E" strokeDasharray="4 4" />
            <text x={(COLS.drill[0] + COLS.drill[1]) / 2} y={y(0) + 38} textAnchor="middle" className="depth__none">{t('depth.noData')}</text>
          </g>
        )}
      </svg>
      <figcaption className="depth__key">
        <div>
          <span className="depth__swatch depth__swatch--water" aria-hidden="true" />
          <strong>{t('depth.waterTitle')}</strong>
          <span className="depth__val">{water ? `${water.range_ft[0]}–${water.range_ft[1]} ${t('unit.ft')}` : t('common.notAvailable')}</span>
        </div>
        <div>
          <span className="depth__swatch depth__swatch--drill" aria-hidden="true" />
          <strong>{t('depth.drillTitle')}</strong>
          <span className="depth__val">{drill ? `${drill.low_ft}–${drill.high_ft} ${t('unit.ft')}` : t('common.notAvailable')}</span>
        </div>
      </figcaption>
    </figure>
  );
}
