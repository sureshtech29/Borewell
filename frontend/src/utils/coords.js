// Parse a pasted/typed coordinate pair. Accepts:
//   17.385, 78.4867      17.385 78.4867      N17.385 E78.4867      17.385°N 78.4867°E
//   17°23'06"N 78°29'12"E    17°23.1'N, 78°29.2'E       (a leading '-' or S/W means south/west)
// If both numbers could only be a longitude followed by a latitude (e.g. 78.48, 17.38) they are swapped and flagged.

// A component has its hemisphere letter either before ("N17.38") or after ("17.38N") - never both, so the two forms are separate patterns.
const NUM = String.raw`(-?\d+(?:\.\d+)?)\s*(?:°|º)?\s*(?:(\d+(?:\.\d+)?)\s*'\s*)?(?:(\d+(?:\.\d+)?)\s*"\s*)?`;
const COMP_PREFIX = new RegExp(String.raw`([NSEW])\s*` + NUM, 'iy');
const COMP_SUFFIX = new RegExp(NUM + String.raw`([NSEW])?`, 'iy');
const SEP = /[\s,;/]*/y;

function normalise(text) {
  return String(text)
    .replace(/[′’‘`´]/g, "'")
    .replace(/[″“”]/g, '"')
    .replace(/''/g, '"')
    .replace(/ /g, ' ')
    .trim();
}

function readComponent(s, pos) {
  let h, deg, min, sec, whole;
  if (/[NSEW]/i.test(s[pos] || '')) {
    COMP_PREFIX.lastIndex = pos;
    const m = COMP_PREFIX.exec(s);
    if (!m) return null;
    [whole, h, deg, min, sec] = m;
  } else {
    COMP_SUFFIX.lastIndex = pos;
    const m = COMP_SUFFIX.exec(s);
    if (!m) return null;
    [whole, deg, min, sec, h] = m;
  }
  const hemi = (h || '').toUpperCase();
  const d = parseFloat(deg);
  const mi = min ? parseFloat(min) : 0;
  const se = sec ? parseFloat(sec) : 0;
  if (mi >= 60 || se >= 60) return { error: 'format' };
  if ((min || sec) && !Number.isInteger(Math.abs(d))) return { error: 'format' };
  let v = Math.abs(d) + mi / 60 + se / 3600;
  if (d < 0 || String(deg).startsWith('-')) v = -v;
  if (hemi === 'S' || hemi === 'W') v = -Math.abs(v);
  return { value: v, hemi, end: pos + whole.length };
}

export function parseCoordinates(text) {
  const s = normalise(text ?? '');
  if (!s) return { ok: false, error: 'empty' };
  const a = readComponent(s, 0);
  if (!a || a.error) return { ok: false, error: 'format' };
  SEP.lastIndex = a.end;
  const gap = SEP.exec(s);
  const b = readComponent(s, a.end + gap[0].length);
  if (!b || b.error) return { ok: false, error: 'format' };
  if (b.end !== s.length) return { ok: false, error: 'format' };

  let lat, lon, swapped = false;
  const isLat = (h) => h === 'N' || h === 'S';
  const isLon = (h) => h === 'E' || h === 'W';
  if (a.hemi || b.hemi) {
    if (isLat(a.hemi) && (isLon(b.hemi) || !b.hemi)) { lat = a.value; lon = b.value; }
    else if (isLon(a.hemi) && (isLat(b.hemi) || !b.hemi)) { lon = a.value; lat = b.value; swapped = true; }
    else if (!a.hemi && isLon(b.hemi)) { lat = a.value; lon = b.value; }
    else if (!a.hemi && isLat(b.hemi)) { lon = a.value; lat = b.value; swapped = true; }
    else return { ok: false, error: 'format' };
  } else {
    lat = a.value; lon = b.value;
    // India: latitude ~6-38, longitude ~68-98. "78.48, 17.38" can only be longitude first.
    const aLooksLon = a.value >= 60 && a.value <= 100, bLooksLat = b.value >= 5 && b.value <= 40;
    const aLooksLat = a.value >= 5 && a.value <= 40, bLooksLon = b.value >= 60 && b.value <= 100;
    if (aLooksLon && bLooksLat && !(aLooksLat && bLooksLon)) { lat = b.value; lon = a.value; swapped = true; }
  }
  if (!(Math.abs(lat) <= 90 && Math.abs(lon) <= 180)) return { ok: false, error: 'range' };
  return { ok: true, lat, lon, swapped };
}

/** "17.38500, 78.48670" */
export function formatLatLon(lat, lon, digits = 5) {
  return `${lat.toFixed(digits)}, ${lon.toFixed(digits)}`;
}

/** True when the point lies inside [[south, west], [north, east]]. */
export function insideBounds(lat, lon, bounds) {
  const [[s, w], [n, e]] = bounds;
  return lat >= s && lat <= n && lon >= w && lon <= e;
}
