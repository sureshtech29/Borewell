export const FT_PER_M = 3.280839895;

export function fmtDate(iso, lang) {
  if (!iso) return '';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === 'te' ? 'te-IN' : 'en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

export function fmtDateTime(iso, lang) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === 'te' ? 'te-IN' : 'en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata',
  }).format(d);
}

export const fmtRange = (r) => (r ? `${r[0]}–${r[1]}` : '');

/** Nice axis maximum above `value` in steps of 100 ft. */
export function niceMax(value, step = 100) {
  return Math.max(step, Math.ceil((value + step * 0.25) / step) * step);
}
