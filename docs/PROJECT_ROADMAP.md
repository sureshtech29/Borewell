# Borewell Water Finder — Product & Technical Upgrade Roadmap

This roadmap extends the existing React + Vite, FastAPI, PostgreSQL/PostGIS application. It does not replace the current scoring engine or imply that the project contains real groundwater observations. The bundled dataset remains synthetic demonstration data.

## Product direction

Position the product as a **Groundwater Intelligence & Smart Borewell Site Screening Platform**. It should help a landowner understand regional groundwater potential, nearby historical evidence, data confidence, and what field investigation is still required. It must never promise water, a specific yield, or drilling success.

## Implemented in this upgrade: plot boundary candidate screening

The map now supports a first version of plot-level screening:

1. Select **Draw plot boundary** and tap at least three plot corners on the map.
2. Submit the boundary to `POST /api/plot-rank`.
3. The API samples a bounded 3 × 3 grid, retains sample points inside the polygon, and runs the existing point-analysis engine for each candidate.
4. Candidate points are sorted by available potential score; missing scores sort last. The response includes potential class, score, confidence level, data mode, and any existing drilling-depth evidence.
5. The frontend lists and maps the ranked candidates. Demo mode is visibly warned against for real decisions.

### Important limitations of this first version

- It samples a regular grid, not every possible point in the plot.
- It uses the existing regional/local point-analysis model; it does not detect plot-scale fractures.
- Candidate rank is a relative screening result, not a probability of finding water.
- A high score or confidence does not guarantee a productive borewell.
- The request is limited to 20 vertices and a bounding-box span of 0.1 degrees in either axis. This is a basic abuse/scope guard, not a surveyed parcel-area calculation.
- The sample grid can produce no candidate points for very small or narrow polygons; the API returns a validation error in that case.
- The UI currently returns candidate scores and existing depth evidence; it does not invent a yield estimate.

## Priority 0 — production data and scientific validation

**Do this before any public or paid drilling recommendation.**

- Acquire authentic Telangana datasets from the relevant official publishers (CGWB, Telangana Ground Water Department, India-WRIS, GSI, IMD, and other properly licensed sources).
- Record publisher, licence, retrieval date, observation period, coordinate reference system, spatial resolution, and processing history for every layer.
- Verify spatial alignment, missingness, units, duplicate wells, date consistency, and location precision before loading.
- Preserve source provenance through the existing ETL and dataset registry.
- Calibrate factor scores and class thresholds with hydrogeologists; current weights and thresholds are expert-assigned starting assumptions.
- Validate with spatially separated holdout areas so nearby wells do not leak between training and testing.
- Report class-wise precision/recall, calibration, coverage, and uncertainty. Do not call the score a probability unless a probability calibration study supports that interpretation.
- Keep ML disabled until the documented real-record and spatial cross-validation gate is met.

## Priority 1 — improve plot-level site screening

- Add polygon geometry validation: self-intersection, closure, area in a suitable projected CRS, and state coverage checks.
- Replace the regular grid with adaptive sampling that respects plot area and data resolution.
- Add candidate explanation: factor availability, local evidence counts, nearest observation well, and why one candidate outranks another.
- Show confidence and data gaps prominently, not only the potential score.
- Allow export of a plot screening report with the boundary, candidates, method version, source dataset versions, and caveats.
- Add a qualified-professional review workflow for any site-specific recommendation.

## Priority 2 — borewell and aquifer evidence

- Add privacy-preserving borewell outcome submissions: drilling date, total depth, water-strike depth, static water level, pumping water level, pump-test discharge, and outcome category.
- Require provenance and verification status; distinguish user-submitted, contractor-submitted, and official records.
- Keep personal names, phone numbers, survey numbers, and exact private property details out of public map layers.
- Distinguish drilling depth, static water level, pumping water level, and tested yield throughout the UI and reports.
- Add time-aware evidence so old records are not treated as current without qualification.

## Priority 3 — geophysical survey workflow

- Support VES and ERT survey metadata, field locations, date, equipment/configuration, interpreted layers, weathered-zone thickness, and fracture-zone intervals.
- Store raw measurements separately from interpreted outputs, with the interpreter, method, software/version, and quality review.
- Do not automatically translate a raw resistivity value into a guaranteed water-bearing fracture. Interpretation needs local geology and qualified professional review.

## Priority 4 — recharge and groundwater monitoring

- Add pre- and post-monsoon observation histories and seasonal trend charts.
- Incorporate rainfall, land use, runoff, soil infiltration, surface water, recharge structures, and extraction context where reliable data exists.
- Build village/mandal dashboards for groundwater condition, data coverage, and trend direction.
- Clearly distinguish measured groundwater levels from modelled recharge or resource indicators.

## Priority 5 — farmer decision support

- Add an irrigation demand calculator using crop, area, season, irrigation method, and locally appropriate crop-water assumptions.
- Compare demand only with measured or qualified pump-test discharge and explain seasonal limitations.
- Add water-quality testing records and separate suitability for drinking from suitability for irrigation.
- Offer English and Telugu explanations; have technical Telugu wording reviewed by a native groundwater specialist.

## Implemented — AI-assisted report explanation

The report now has an optional **Explain this report with AI** action. The API uses an OpenAI-compatible chat-completions endpoint configured on the server (`AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`). The API key is never sent to the browser. The endpoint whitelists report fields and excludes exact coordinates and unrelated user fields before sending context to the provider. It supports English and Telugu, applies an eight-request-per-hour per-client limit, and returns a clear not-configured response when no key is set.

**Critical distinction:** this AI feature explains the existing report; it does not make the groundwater model more accurate, validate datasets, discover hidden fractures, or create a reliable probability of drilling success. AI output can be wrong. Real-world accuracy still depends on authentic current datasets, qualified hydrogeological review, and spatially independent validation against actual borewell outcomes.

## Priority 6 — AI assistant and business workflows

- Extend explanations only when new verified report fields and source citations are available.
- Cite the data source and date in each explanation; answer "unknown" when evidence is missing.
- Never let the assistant fabricate a yield, depth, water quality, or drilling success probability.
- Later consider professional subscriptions, institutional dashboards, and verified surveyor/contractor directories, with clear separation between paid services and unbiased groundwater assessments.

## Suggested database additions

| Table | Purpose |
|---|---|
| `plots` | User-owned plot boundaries with consent and access controls |
| `candidate_sites` | Candidate point, rank, model version, and run metadata |
| `field_surveys` | VES/ERT survey metadata and interpretations |
| `pump_tests` | Measured discharge and pumping-test observations |
| `borewell_observations` | Time-series water-level measurements |
| `groundwater_predictions` | Reproducible prediction history and validation metadata |
| `data_quality` | Source quality, processing, verification, and temporal coverage |

Before adding these tables, define retention, consent, role-based access, and exact-location privacy requirements.

## Release checklist

- [ ] Replace synthetic demo data with licensed and quality-checked official data.
- [ ] Hydrogeologist review of Telangana factor tables and class thresholds.
- [ ] Spatial holdout validation and documented performance by geological setting.
- [ ] Validate polygon geometry and sampling against a projected CRS.
- [ ] Confirm privacy and consent for plot boundaries and borewell observations.
- [ ] Review Telugu technical translations.
- [ ] Configure licensed map tiles, HTTPS, backups, monitoring, and dependency locks.
- [ ] Test the complete frontend, backend, Docker, and PDF flows before release.

## Immediate next development step

Harden plot screening with robust geometry validation, adaptive sampling, candidate explanation, and a downloadable plot report. Only then proceed to new prediction features. Scientific validation and real-data acquisition remain the release gate.
