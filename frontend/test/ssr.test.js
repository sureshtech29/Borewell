// Smoke tests: render the real report/page components to HTML for every demo fixture, in English and Telugu.
// Needs: react, react-dom and esbuild (installed by `npm install`; esbuild comes with vite).
// react-router-dom is used if installed, otherwise a tiny stand-in (test/ssr/router-shim.jsx).
import { test, before } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync, readdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import en from '../src/i18n/en.js';
import te from '../src/i18n/te.js';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const FX = join(here, 'fixtures');
const read = (f) => JSON.parse(readFileSync(join(FX, f), 'utf8'));
const meta = read('meta.json');
const analyses = Object.fromEntries(readdirSync(FX).filter((f) => f.startsWith('analysis_')).map((f) => [f.slice(9, -5), read(f)]));
const COLORS = Object.fromEntries(meta.legend.map((l) => [l.key, l.color]));

let ui;
before(async () => {
  const esbuild = require('esbuild');
  let haveRouter = true;
  try { require.resolve('react-router-dom'); } catch { haveRouter = false; }
  const shim = { name: 'router-shim', setup(b) { if (!haveRouter) b.onResolve({ filter: /^react-router-dom$/ }, () => ({ path: join(here, 'ssr', 'router-shim.jsx') })); } };
  const outfile = join(mkdtempSync(join(tmpdir(), 'bwf-ssr-')), 'ui.mjs');
  await esbuild.build({
    entryPoints: [join(here, 'ssr', 'entry.jsx')], outfile, bundle: true, format: 'esm', platform: 'node', jsx: 'automatic',
    loader: { '.js': 'jsx' }, plugins: [shim], logLevel: 'error', nodePaths: (process.env.NODE_PATH || '').split(':').filter(Boolean),
    banner: { js: "import { createRequire as __cr } from 'node:module'; const require = __cr(import.meta.url);" },
  });
  ui = await import(pathToFileURL(outfile).href);
});

const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&[a-z#0-9]+;/g, ' ').replace(/\s+/g, ' ');
const LEAKS = [/undefined/, /\[object Object\]/, /\bNaN\b/, /\bnull\b/];

function assertClean(html, lang, label) {
  const tx = text(html);
  for (const re of LEAKS) assert.doesNotMatch(tx, re, `${label}: leaked ${re} in visible text`);
  const dict = lang === 'te' ? te : en;
  // a missing translation key is rendered as the key itself, e.g. ">report.verdict<"
  for (const k of Object.keys(dict)) assert.ok(!html.includes(`>${k}<`), `${label}: raw key "${k}" is visible`);
  assert.doesNotMatch(tx, /\{\w+\}/, `${label}: unreplaced {placeholder}`);
}

for (const lang of ['en', 'te']) {
  for (const [name, a] of Object.entries(analyses)) {
    for (const variant of ['panel', 'page']) {
      test(`report ${name} [${lang}/${variant}]`, () => {
        const html = ui.renderReport({ lang, meta, analysis: a, variant });
        const label = `${name}/${lang}/${variant}`;
        assertClean(html, lang, label);
        // verdict colour is the API colour for the class, never another class's colour
        const m = html.match(/--cls:\s*(#[0-9A-Fa-f]{6})/);
        assert.ok(m, `${label}: verdict colour missing`);
        assert.equal(m[1].toUpperCase(), COLORS[a.potential.class].toUpperCase());
        // the API's own wording for the class and its potential-vs-confirmed note are on screen
        const headline = a.status === 'ok' ? a.potential.label[lang] : a.status_title[lang];
        assert.ok(text(html).includes(headline), `${label}: headline "${headline}" not shown`);
        assert.ok(text(html).includes(a.potential.note[lang].slice(0, 40)), `${label}: potential note not shown`);
        assert.ok(text(html).includes(a.disclaimer[lang].slice(0, 40)), `${label}: disclaimer not shown`);
        if (lang === 'te') assert.match(html, /[ఀ-౿]/, `${label}: no Telugu script`);
        // demo data is always labelled
        if (a.is_demo) assert.match(html, /report__demo/, `${label}: demo label missing`);

        const d = a.drilling_depth;
        if (a.status === 'ok' && d.available) {
          assert.ok(html.includes(`${d.low_ft}–${d.high_ft}`), `${label}: drilling range not shown`);
        }
        if (a.status === 'ok' && !d.available) {
          // data-supported only: no drilling range, and the reason is shown instead
          assert.doesNotMatch(html, /class="fact__big">\d+–\d+[^<]*<\/p>\s*<p class="fact__line">[^<]*productive/, `${label}: depth range shown without data`);
          assert.match(html, /fact__none/, `${label}: "not available" message missing`);
        }
        if (a.status !== 'ok') {
          assert.equal(a.potential.class, 'insufficient_data');
          assert.doesNotMatch(html, /id="depth-h"/, `${label}: depth section shown for out-of-coverage point`);
        }
      });
    }
  }
}

for (const lang of ['en', 'te']) {
  for (const page of ['header', 'footer', 'banner', 'legend', 'home', 'about', 'contact']) {
    test(`page ${page} [${lang}]`, () => {
      const html = ui.renderPage({ lang, meta, page });
      assert.ok(html.length > 50, 'rendered something');
      assertClean(html, lang, `${page}/${lang}`);
      if (lang === 'te' && page !== 'banner') assert.match(html, /[ఀ-౿]/);
    });
  }
  test(`report page without a point [${lang}]`, () => {
    const html = ui.renderPage({ lang, meta, page: 'report', url: '/report' });
    assertClean(html, lang, 'report-nopoint');
    assert.match(html, /href="\/map"/);
  });
  test(`report page with a point shows loading, not data [${lang}]`, () => {
    const html = ui.renderPage({ lang, meta, page: 'report', url: '/report?lat=17.45&lon=78.35' });
    assertClean(html, lang, 'report-loading');
    assert.match(html, /role="status"/);
  });
}

test('legend colours are the five specified, in order, and the grey is "insufficient data"', () => {
  assert.deepEqual(meta.legend.map((l) => l.key), ['high', 'moderate', 'low', 'very_low', 'insufficient_data']);
  assert.deepEqual(meta.legend.map((l) => l.color.toUpperCase()), ['#1E6FD9', '#2E9E4F', '#F2C230', '#D64545', '#9AA3AD']);
  const html = ui.renderPage({ lang: 'en', meta, page: 'legend' });
  for (const l of meta.legend) assert.ok(html.toUpperCase().includes(l.color.toUpperCase()));
});
