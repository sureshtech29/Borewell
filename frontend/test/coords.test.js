import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCoordinates, insideBounds } from '../src/utils/coords.js';

const near = (a, b, eps = 1e-4) => assert.ok(Math.abs(a - b) < eps, `${a} !~ ${b}`);

test('decimal pairs', () => {
  for (const s of ['17.385, 78.4867', '17.385 78.4867', '17.385;78.4867', ' 17.385 ,78.4867 ', '17.385/78.4867']) {
    const r = parseCoordinates(s);
    assert.ok(r.ok, s); near(r.lat, 17.385); near(r.lon, 78.4867); assert.equal(r.swapped, false);
  }
});

test('hemisphere letters, prefix or suffix, any order', () => {
  let r = parseCoordinates('N17.385 E78.4867'); near(r.lat, 17.385); near(r.lon, 78.4867);
  r = parseCoordinates('17.385°N 78.4867°E'); near(r.lat, 17.385); near(r.lon, 78.4867);
  r = parseCoordinates('78.4867E, 17.385N'); near(r.lat, 17.385); near(r.lon, 78.4867); assert.equal(r.swapped, true);
  r = parseCoordinates('17.385 S, 78.4867 W'); near(r.lat, -17.385); near(r.lon, -78.4867);
});

test('degrees minutes seconds', () => {
  let r = parseCoordinates('17°23\'06"N 78°29\'12"E');
  near(r.lat, 17 + 23 / 60 + 6 / 3600); near(r.lon, 78 + 29 / 60 + 12 / 3600);
  r = parseCoordinates('17°23.1′N, 78°29.2′E'); near(r.lat, 17 + 23.1 / 60); near(r.lon, 78 + 29.2 / 60);
  r = parseCoordinates('17° 23′ 06″ N 78° 29′ 12″ E'); near(r.lat, 17.385);
});

test('longitude-first pairs inside India are swapped and flagged', () => {
  const r = parseCoordinates('78.4867, 17.385');
  assert.ok(r.ok && r.swapped); near(r.lat, 17.385); near(r.lon, 78.4867);
});

test('rejects nonsense, out-of-range numbers and trailing junk', () => {
  assert.deepEqual(parseCoordinates(''), { ok: false, error: 'empty' });
  assert.equal(parseCoordinates('Hyderabad').error, 'format');
  assert.equal(parseCoordinates('17.385').error, 'format');
  assert.equal(parseCoordinates('17.385, 78.4867, 5').error, 'format');
  assert.equal(parseCoordinates('95.0, 78.0').error, 'range');
  assert.equal(parseCoordinates('17.0, 190.0').error, 'range');
  assert.equal(parseCoordinates('17°75\'00"N 78°E').error, 'format');
});

test('insideBounds', () => {
  const b = [[15.8, 77.2], [19.95, 81.8]];
  assert.ok(insideBounds(17.4, 78.4, b));
  assert.ok(!insideBounds(12.9, 77.6, b));
});
