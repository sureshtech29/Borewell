/** A selected site lives in the URL (?lat=..&lon=..&acc=..) so it can be shared, bookmarked and reached with the back button. */
export function pointSearch(p) {
  const q = new URLSearchParams({ lat: p.lat.toFixed(6), lon: p.lon.toFixed(6) });
  if (p.accuracy > 0) q.set('acc', String(Math.round(p.accuracy)));
  return q.toString();
}

export function pointFromParams(params, source) {
  const lat = Number.parseFloat(params.get('lat'));
  const lon = Number.parseFloat(params.get('lon'));
  if (!(Math.abs(lat) <= 90) || !(Math.abs(lon) <= 180)) return null;
  const acc = Number.parseFloat(params.get('acc'));
  return { lat, lon, accuracy: acc > 0 ? acc : undefined, source };
}
