# Borewell Water Finder · భూగర్భ జలాల అన్వేషణ

A web app that helps farmers, landowners and drillers judge the **groundwater potential** of a spot before they
drill a borewell. Pick a place on the map, use GPS, type coordinates, or search by district, mandal, village or PIN
code. You get a plain-language report: the potential class, how deep the water table stood in nearby monitoring wells,
how deep nearby borewells were drilled (only where records exist), how much real data stands behind the answer, what
is missing, and what to do next. English and Telugu throughout, with a downloadable PDF.

**It estimates potential. It never confirms water and never promises drilling success.** Where data is missing the
app says so (grey, "insufficient data") instead of filling the gap.

> **Status: complete application, demonstration data only.** The repository ships with *synthetic* sample data,
> labelled as such on every screen and in every PDF. No real groundwater data is bundled. Do not use the demo for any
> real decision. Before real use read [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) ("Before real people rely on
> this") and [`docs/DATA_INTEGRATION.md`](docs/DATA_INTEGRATION.md).

| Map colour | Meaning |
|---|---|
| Blue | High groundwater potential |
| Green | Moderate |
| Yellow | Low |
| Red | Very low |
| Grey | Insufficient data (does **not** mean there is no water) |

## Quick start (Docker)

```bash
cp .env.example .env            # set POSTGRES_PASSWORD (letters and digits)
docker compose up --build
# open http://localhost:8080
```

This starts PostGIS (seeded with the synthetic data), the API and the web server. The API container publishes no
port: only the web container's nginx can reach it, because the API's rate limiter trusts the `X-Real-IP` header that
nginx sets.

## Quick start (no Docker)

```bash
# 1. API on the in-memory demo data (needs Python 3.11+)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --no-access-log          # http://localhost:8000/docs

# 2. Web app (needs Node 20+), in another terminal
cd frontend
npm install
npm run dev                                           # http://localhost:5173, /api is proxied to :8000
```

Without `DATABASE_URL` the API uses its in-memory backend, which holds synthetic demo data only. It refuses to start in
`APP_DATA_MODE=production`.

## What is in the repository

```
backend/                FastAPI app, scoring engine, PostGIS repository, ETL loaders, tests
  app/engine/             regional index, local evidence, water table, depth range, confidence, optional ML gate
  app/repository/         memory (demo) and postgis implementations of one interface
  app/routers/            /api endpoints
  app/reports/            report template -> HTML -> PDF (WeasyPrint)
  config/states/          one YAML per state: classes, factor tables, thresholds, alias maps, Telugu labels
  db/                     schema.sql, seed_demo.sql (synthetic), docker-init.sh
  demo/                   generator of the synthetic dataset
  scripts/etl/            load real data;  scripts/compute_potential.py;  scripts/train_model.py
frontend/               React + Leaflet web app (Vite), nginx config, Dockerfile
docs/                   METHODOLOGY.md, DATA_INTEGRATION.md
docker-compose.yml      db + api + web (+ a `tools` profile for data jobs)
```

### Pages

Home, interactive map (street / satellite, GPS button, click or drag the pin, coordinates box, search, browse by
district → mandal → village), analysis report (side panel and full page), PDF download, About (sources, limits,
privacy) and Contact. The language switcher is in the header; the choice is remembered.

### Plot-level candidate screening (new)

On the map page, choose **Draw plot boundary**, tap at least three corners, and submit the boundary to rank sample candidate locations. The application samples a 3 × 3 grid inside the polygon and runs the existing point-analysis engine at each sample. Ranked points are shown on the map and in a list with potential score/class and confidence. The endpoint is `POST /api/plot-rank`.

This is an initial regional screening aid, not a plot-scale fracture detector or a drilling recommendation. It cannot replace VES/ERT, a pump test, or qualified hydrogeologist review. It uses the same underlying data mode as the rest of the app; in demo mode all results are synthetic and must not guide real drilling. See [`docs/PROJECT_ROADMAP.md`](docs/PROJECT_ROADMAP.md) for the full product direction, implementation notes, and release gates.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness |
| `GET /api/meta` | data mode, legend, method and factor weights, state info (the web app reads this at start-up) |
| `GET /api/datasets` | every data source with publisher, licence, dates and whether it is demo data |
| `GET /api/analyze?lat=&lon=&accuracy_m=` | the analysis for one point (bilingual text) |
| `POST /api/plot-rank` | rank a bounded set of sample points inside a user-drawn plot boundary |
| `GET /api/search?q=` | places (English or Telugu) and PIN codes |
| `GET /api/regions?level=&parent_id=` | district / mandal / village lists for browsing |
| `GET /api/layers/potential?bbox=` | GeoJSON cells for the coloured layer (bbox is capped; the response says when truncated) |
| `GET /api/layers/wells?bbox=` · `/borewells?bbox=` · `/coverage` | monitoring wells, record points (off in production), covered area |
| `GET /api/report/html` · `/pdf?lat=&lon=&lang=` | printable report; `pdf` returns 501 `pdf_unavailable` if WeasyPrint is missing |
| `POST /api/contact` | contact form (5 per hour per client) |

Interactive docs at `/docs` when the API runs directly.


### Optional AI report explanation

The report page includes an AI explanation button. To enable it, set `AI_API_KEY` in the server-side `.env` file. `AI_BASE_URL` and `AI_MODEL` can point to an OpenAI-compatible chat-completions provider. Restart with `docker compose up --build -d api`. Keep the key private: do not use a `VITE_` variable or put it in frontend code. The AI endpoint is rate-limited and receives only a whitelist of report evidence fields, not the selected coordinates.

AI is an explanation aid, not a groundwater prediction engine. It does not improve prediction accuracy or validate the source data. The current bundled database may still contain synthetic demo data; the AI will explicitly warn about demo mode. Do not use demo results or AI explanations to decide where to drill.

## Switching to real data

1. Download the datasets from the official sources and load them with the ETL commands:
   [`docs/DATA_INTEGRATION.md`](docs/DATA_INTEGRATION.md) lists each file, its columns and where it usually comes from.
2. `python -m scripts.compute_potential` to pre-compute the map layer.
3. Set in `.env`: `APP_DATA_MODE=production` and `SEED_DEMO=false` (for a fresh database), then restart.

In production mode the API reads only rows with `is_demo = false`, hides individual borewell points, and the interface
shows no demonstration banner. Demo rows can stay in the database; they cannot reach a production analysis. A fresh,
empty production database starts fine and reports every point as "outside the covered area" until data is loaded.

## Privacy

- **Coordinates are not stored or logged.** The API runs with `--no-access-log` (an access log would contain the query
  string), the shipped nginx log format omits query strings and the Referer, and the app sets
  `Referrer-Policy: strict-origin-when-cross-origin` so map-tile providers never see the page URL with its coordinates.
  If you put another proxy or CDN in front, switch off query-string logging there too.
- The selected place lives in the page URL (`?lat=&lon=`) so a link can be shared. Anyone you send the link to sees that
  place. Tell users before they share a farm location.
- GPS is used only when the user presses the button, and the browser asks first.
- **The contact form stores** name, email, optional phone and message in the database. Delete them on a schedule you
  state in your privacy notice.
- Borewell loading never stores owner names, phone numbers or survey numbers.

## Map tiles: read this before going public

The defaults (OpenStreetMap standard tiles; Esri World Imagery for satellite) are for development and light use. Their
usage policies do not allow a busy public site to rely on them, and the imagery has its own terms and attribution
rules. For a real deployment choose a tile provider you have an agreement with and set the `VITE_TILE_*` variables
(`.env.example`). Keep the attribution the provider requires; the app shows it on the map.

## Deployment notes

- Put TLS in front (a load balancer, Caddy, or nginx with certificates). GPS in browsers works only on HTTPS (and
  `localhost`).
- If a proxy sits in front of the web container, configure nginx's `set_real_ip_from` (commented in
  `frontend/nginx.conf.template`) so the rate limiter sees the client rather than the proxy.
- Back up the `pgdata` volume. The loaded data is reproducible from your source files; contact messages are not.
- Pin and lock dependencies for production: run `npm install` once and commit `package-lock.json`; freeze
  `backend/requirements.txt` with a lock file. The versions in the repository are ranges.
- PDF output needs WeasyPrint plus Pango and Telugu fonts. The API Dockerfile installs them. Without them the PDF button
  falls back to the printable HTML page ("Save as PDF" from the browser).
- The API `Dockerfile` runs as a non-root user; the web image uses `nginx-unprivileged` on port 8080.

## Tests

```bash
cd backend  && pip install -r requirements-dev.txt && python -m pytest        # engine, API contract, ETL, PDF/HTML
cd frontend && npm install && npm test                                        # coordinate parser, i18n, rendered pages (EN/TE)
```

The fixtures are real API output on the synthetic data; regenerate them with `python -m scripts.make_frontend_fixtures`
(from `backend/`) after changing the demo data or the response shape. The frontend render tests build the real components with demo API output (`frontend/test/fixtures/`) and check, for
every potential class and for out-of-coverage points, in both languages, that: nothing renders `undefined` or a raw
translation key, the verdict colour is the API's colour for that class, the "potential is not confirmed water" note and
the disclaimer are present, demo data is labelled, and no depth range appears unless the API supplied one.

## Adding another state

See "Adding another state" in [`docs/DATA_INTEGRATION.md`](docs/DATA_INTEGRATION.md). In short: a new YAML file whose
every table is reviewed by a hydrogeologist who knows that state, then the same loaders.

## Known limits and open items

- Plot-level candidate screening is a regular-grid sample of the existing point model. It is not plot-scale geophysics and is not validated as a drilling-point predictor; see `docs/PROJECT_ROADMAP.md`.

- **The scoring is not calibrated.** Weights, class scores and thresholds are expert-assigned priors and placeholder
  cut-offs. They need review and validation against real borewell outcomes before anyone relies on the classes
  (`docs/METHODOLOGY.md`).
- **No real data is bundled** and the loaders have been tested only on synthetic files. The IMD `.GRD` layout is implemented
  from IMD's published description; check it against one real file with `--dry-run`.
- **Telugu text needs review by a native speaker** with groundwater vocabulary.
- Fonts come from the `@fontsource` packages (Atkinson Hyperlegible for Latin, Noto Sans Telugu for Telugu).
- The statistical model stays switched off until there are at least 500 real records and it passes spatial
  cross-validation. On the demo data it correctly fails the gate.
- The app does not give legal, regulatory or permission advice. It tells users to check drilling permission and
  registration rules with the State Ground Water Department.

## Licence

No licence file is included. Add the one you intend before publishing. Data you load keeps its publisher's licence;
record it in each source (`--license`) so the app can show it.

### Live location
On the Map page, press **Use my location** and allow location access in your browser/device prompt. The map will follow your device while live location is enabled; press **Stop live location** to stop sharing. Geolocation requires HTTPS on a deployed website (localhost is permitted for development). The browser may provide GPS, Wi-Fi or other device-derived positioning; accuracy varies. This feature locates the user and does not make groundwater observations live.
