# Upgrade notes

## Existing upgrade
- Added plot-boundary candidate screening using the existing point-analysis engine.
- Added the product roadmap and implementation priorities.

## AI report explanation upgrade
- Added `POST /api/ai/explain`, an optional OpenAI-compatible report explanation endpoint.
- Added English and Telugu report explanation controls.
- AI credentials are read only by the backend from environment variables.
- Exact selected coordinates and non-whitelisted fields are excluded from the provider prompt.
- Added per-client AI rate limiting and a clear not-configured response.
- Added `docs/AI_EXPLANATION.md` and server-side environment configuration.
- Added backend tests for configuration, report field filtering, and language validation.

## Verification
- Backend: 116 tests passed.
- Frontend: i18n and coordinate tests passed (11); SSR tests could not run because `esbuild` is not installed in this environment. Install frontend dependencies with `npm ci` (if a lockfile is supplied) or `npm install`, then run `npm test` and `npm run build`.
- AI requires an administrator-supplied `AI_API_KEY`; it is intentionally disabled by default.

## Important
AI explains existing report evidence. It does not improve prediction accuracy or validate groundwater data. Real-data integration and independent hydrogeological validation remain required before real drilling use.

## PIN search fix — 500032
- Added the two India Post-listed post-office entries for PIN `500032`: Gachibowli S.O and MANUU S.O.
- Added a regression test for exact PIN search and its two results.
- The map uses a shared approximate PIN-area centre for these demo records; it is not a verified office coordinate or postal boundary.
- Existing PostGIS installations can apply `backend/db/fix_pincode_500032.sql` once. Fresh demo databases receive the records from `backend/db/seed_demo.sql`.
- All records remain `is_demo=true`. This fixes search coverage only; it does not add real groundwater measurements or confirm groundwater potential.

## Live GPS location update
- The map's location control now starts/stops user-consented live GPS tracking with `watchPosition`.
- The map marker follows the device as it moves; tiny GPS jitter under 20 metres is ignored to avoid unnecessary repeat analysis requests.
- Tracking stops when the user presses the button again or leaves the map page. No background tracking is performed.
- Browser/device location permission is required. Production deployment must use HTTPS (localhost is allowed for local development). GPS accuracy depends on the device, signal and environment; it is not a surveyed property boundary.
