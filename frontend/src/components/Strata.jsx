import { useI18n } from '../i18n/index.jsx';

/**
 * Hero illustration: a cross-section of the ground with ONE borewell. It teaches the idea the whole site rests on -
 * the water table is one depth, the depth you have to drill is another, and only drilling confirms water.
 * Illustrative, not to scale, and not any real site (said in the caption). Neutral earth tones + violet only.
 */
export default function Strata() {
  const { t } = useI18n();
  const labels = [
    { y: 70, text: t('strata.soil') },
    { y: 130, text: t('strata.weathered') },
    { y: 215, text: t('strata.fractured') },
    { y: 295, text: t('strata.massive') },
  ];
  return (
    <figure className="strata">
      <svg viewBox="0 0 420 360" role="img" aria-label={t('strata.alt')}>
        <defs>
          <pattern id="s-dots" width="9" height="9" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#A99B88" /></pattern>
          <pattern id="s-cross" width="14" height="14" patternUnits="userSpaceOnUse"><path d="M0 0l14 14M14 0L0 14" stroke="#8E959B" strokeWidth=".8" /></pattern>
          <pattern id="s-crack" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M3 4l9 8-5 9 12 7M22 2l-4 10 8 6" fill="none" stroke="#6F777D" strokeWidth="1" /></pattern>
        </defs>
        {/* layers */}
        <rect x="70" y="40" width="340" height="52" fill="#D9CDBB" />
        <rect x="70" y="40" width="340" height="52" fill="url(#s-dots)" />
        <path d="M70 92 Q150 100 230 90 T410 94 V170 Q330 178 250 168 T70 172Z" fill="#C2B7A8" />
        <path d="M70 172 Q150 180 250 168 T410 170 V262 Q320 270 240 258 T70 264Z" fill="#B3B8BC" />
        <path d="M70 172 Q150 180 250 168 T410 170 V262 Q320 270 240 258 T70 264Z" fill="url(#s-crack)" />
        <path d="M70 264 Q150 272 240 258 T410 262 V330 H70Z" fill="#9AA0A6" />
        <path d="M70 264 Q150 272 240 258 T410 262 V330 H70Z" fill="url(#s-cross)" />
        {/* ground surface */}
        <path d="M70 40H410" stroke="#2B1B57" strokeWidth="2.5" />
        {/* water table (dashed) */}
        <path d="M70 142 Q160 134 250 142 T410 138" fill="none" stroke="#6A4FC4" strokeWidth="2.5" strokeDasharray="7 5" />
        {/* borewell */}
        <g className="strata__well">
          <path d="M236 22V40" stroke="#2B1B57" strokeWidth="4" strokeLinecap="round" />
          <path pathLength="1" d="M236 40V290" stroke="#2B1B57" strokeWidth="5" strokeLinecap="round" className="strata__bore" />
        </g>
        {/* depth scale */}
        <g className="strata__axis">
          <path d="M52 40V330" stroke="#5B6770" strokeWidth="1" />
          {[0, 100, 200, 300, 400].map((ft, i) => (
            <g key={ft}><path d={`M46 ${40 + i * 72}h12`} stroke="#5B6770" /><text x="40" y={44 + i * 72} textAnchor="end">{ft}</text></g>
          ))}
          <text x="52" y="22" textAnchor="middle" className="strata__unit">{t('unit.ft')}</text>
        </g>
        {/* labels */}
        {labels.map((l) => <text key={l.text} x="82" y={l.y} className="strata__lab">{l.text}</text>)}
        <g className="strata__callouts">
          <path d="M300 140h60" stroke="#6A4FC4" /><text x="304" y="128" className="strata__call strata__call--w">{t('strata.water')}</text>
          <path d="M240 290h50" stroke="#2B1B57" /><text x="296" y="294" className="strata__call">{t('strata.drill')}</text>
        </g>
      </svg>
      <figcaption>{t('strata.caption')}</figcaption>
    </figure>
  );
}
