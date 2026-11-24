import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import en from '../src/i18n/en.js';
import te from '../src/i18n/te.js';

const params = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',');

test('English and Telugu have exactly the same keys', () => {
  const a = Object.keys(en).sort(), b = Object.keys(te).sort();
  assert.deepEqual(a.filter((k) => !(k in te)), [], 'missing in te');
  assert.deepEqual(b.filter((k) => !(k in en)), [], 'missing in en');
});

test('placeholders match between languages', () => {
  for (const k of Object.keys(en)) assert.equal(params(te[k]), params(en[k]), `placeholders differ for ${k}`);
});

test('no empty strings; Telugu strings really contain Telugu script (except unit/abbreviation-only ones)', () => {
  for (const [k, v] of Object.entries(te)) {
    assert.ok(v.trim().length > 0, k);
    assert.ok(/[ఀ-౿]/.test(v), `no Telugu characters in te[${k}]`);
  }
  for (const [k, v] of Object.entries(en)) assert.ok(v.trim().length > 0, k);
});

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : /\.(jsx?|mjs)$/.test(f) ? [p] : [];
  });
}

test('every static t("key") used in the source exists', () => {
  const used = new Set();
  for (const f of walk('src')) {
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(/\bt\('([^']+)'/g)) used.add(m[1]);
    for (const m of src.matchAll(/\? '((?:err|water|search|contact|gps|map)\.[\w.]+)' *: *'((?:err|water|search|contact|gps|map)\.[\w.]+)'/g)) { used.add(m[1]); used.add(m[2]); }
  }
  const missing = [...used].filter((k) => !(k in en));
  assert.deepEqual(missing, []);
});

test('dynamic key families are complete', () => {
  const need = [
    ...['high', 'moderate', 'low', 'very_low', 'insufficient_data'].map((k) => `legend.${k}`),
    ...['state', 'district', 'mandal', 'village', 'pincode'].map((k) => `search.type.${k}`),
    ...['unsupported', 'denied', 'timeout', 'unavailable'].map((k) => `gps.err.${k}`),
    ...['zoomIn', 'zoomMore', 'layerError'].map((k) => `map.hint.${k}`),
    ...['swapped', 'browse', 'outside'].map((k) => `map.note.${k}`),
    ...['need', 'rate', 'invalid', 'network', 'server'].map((k) => `contact.err.${k}`),
    ...['network', 'rate', 'invalid', 'server'].map((k) => `err.${k}`),
    ...['t1', 't2', 't3', 't4'].map((k) => `home.tells.${k}`), ...['o1', 'o2', 'o3', 'o4'].map((k) => `home.only.${k}`),
    ...['cgwb', 'wris', 'gsi', 'tgwd', 'imd'].flatMap((s) => [`home.src.${s}.n`, `home.src.${s}.d`]),
    ...[1, 2, 3, 4, 5].map((n) => `about.limits.${n}`), ...[1, 2, 3, 4].map((n) => `about.privacy.${n}`),
    'water.trendFalling', 'water.trendRising', 'water.trendStable', 'search.coordRange', 'search.coordFormat',
  ];
  assert.deepEqual(need.filter((k) => !(k in en)), []);
});
