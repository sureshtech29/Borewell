# Data integration: loading real data

The app ships with **synthetic demonstration data only**. This page explains how to replace it with real data.
Nothing in this project downloads data for you: the official portals need a manual download and, in most cases,
acceptance of their licence terms. The loaders (`backend/scripts/etl/`) take the files you downloaded, check every
row, and refuse to load anything they cannot vouch for.

Rules the loaders enforce, so the app stays honest:

- Real rows are always stored with `is_demo = false`. A source whose id was registered as a demo source is rejected.
- Every dataset must be registered first with `source` (publisher, licence, last-updated date). The report shows these.
- A blank cell stays `NULL`. Nothing is filled in, interpolated or guessed during loading. A factor with no data is
  reported as "no data" and lowers confidence.
- If any row is invalid the whole file is rejected (use `--skip-invalid` only if you have looked at the errors).
- `--dry-run` runs the full load inside a transaction and rolls it back. Use it first, always.
- Borewell loading never reads or stores owner names, phone numbers or survey numbers, even if the file has them.

## Where the data comes from

> **Check every portal yourself.** Portals reorganise their download pages and change terms. The notes below say what
> each organisation is generally the right source for; they are not a promise about what is currently downloadable,
> in what format, or under what licence. Record the licence you actually found in the `--license` field.

| Layer | Usually published by | Notes |
|---|---|---|
| Water-level observation wells and readings | Central Ground Water Board (CGWB) and the Telangana State Ground Water Department; also via India-WRIS | The most important input. Look for station list + periodic depth-to-water readings (pre-/post-monsoon at least). Units must be **metres below ground level**. |
| Groundwater resource assessment category (safe / semi-critical / critical / over-exploited) | CGWB / State Ground Water Department (Dynamic Ground Water Resources reports) | Optional label on mandal/district polygons (`admin --gw-category-field`). |
| Aquifer maps | CGWB National Aquifer Mapping (NAQUIM) | Polygons with an aquifer type. Mapped by alias to the five standard classes. |
| Geology | Geological Survey of India (GSI), e.g. through Bhukosh | Polygons with a lithology/formation text. Mapped by alias to the nine standard classes. |
| Lineaments / structure | GSI, Bhuvan (NRSC/ISRO) thematic data | Used offline to derive `lineament_density`. |
| Soil | NBSS&LUP / State soil survey, Bhuvan | Polygons with a texture/soil type. |
| Rainfall | India Meteorological Department (IMD), 0.25° gridded daily rainfall | Binary `.GRD` files, one per year. |
| Elevation (DEM) | Bhuvan CartoDEM, SRTM, ALOS or similar | Used offline to derive slope, topographic position and drainage density. |
| Administrative boundaries (district, mandal, village) | Survey of India / state revenue department / LGD; Telangana open-data portals | The mandal/village level is what makes "search by mandal / village" work. |
| PIN code locations | India Post (data.gov.in has post-office directories) | Used for PIN search. Check the lat/lon quality: many directories have none. |
| Historical borewell records | State Ground Water Department, rural water-supply schemes, research projects | **Sensitive.** Strip personal data before it reaches this project (the loader will not store it anyway). Check you are allowed to use and display it. |
| Geophysical surveys (VES / ERT) | State Ground Water Department, CGWB, research projects | Optional but valuable; they are the only layer that sees below the surface at a point. |

If a layer is not available, **leave it out**. The app reports it as missing in the "What is missing" list of every
report. That is the intended behaviour. Do not substitute a "reasonable" value.

## Order of operations

All commands run from `backend/` (or through Docker, see below). They need `DATABASE_URL`, and `psycopg` installed.

```bash
cd backend
export DATABASE_URL=postgresql://bwf:PASSWORD@localhost:5432/bwf
python -m scripts.etl.load state --status planned
python -m scripts.etl.load source ...             # once per dataset, see below
python -m scripts.etl.load admin ...              # district, then mandal, then village
python -m scripts.etl.load admin-link             # links mandals to districts, villages to mandals, PIN codes to districts
python -m scripts.etl.load pincodes ...
python -m scripts.etl.load geology ...            # and soil, aquifer
python -m scripts.etl.load grid ...
python -m scripts.etl.load rainfall-imd ...
python -m scripts.etl.load grid-rainfall ...
python -m scripts.etl.load wells ...
python -m scripts.etl.load borewells ...          # optional
python -m scripts.etl.load ves ...                # optional
python -m scripts.etl.load coverage --status partial
python -m scripts.compute_potential               # pre-computes the coloured map layer
```

With Docker Compose put your files in `./data` (mounted read-only at `/data`) and run, for example:

```bash
docker compose --profile tools run --rm tools python -m scripts.etl.load --dry-run geology \
    --file /data/geology.geojson --source-id gsi_geology --field LITHO
```

Global options (`--state`, `--database-url`, `--dry-run`, `--skip-invalid`) go **before** the command name.

### 1. State and sources

```bash
python -m scripts.etl.load state --status planned

python -m scripts.etl.load source \
    --source-id cgwb_gwl_2025 \
    --name-en "CGWB groundwater level monitoring, Telangana" \
    --publisher "Central Ground Water Board" \
    --kind water_level \
    --license "Paste the licence / terms you found, or the URL of the terms page" \
    --last-updated 2025-11-30 \
    --retrieved-on 2026-01-15 \
    --url "https://..." \
    --notes "Pre- and post-monsoon readings, 2015-2025"
```

`--kind` is one of: `admin, pincode, geology, soil, aquifer, terrain, drainage, lineament, rainfall, water_level,
borewell, geophysics, gw_assessment, other`. `--last-updated` must be the newest observation or publication date
**in the data**, not the day you downloaded it: it is shown to users as "data last updated".

### 2. Administrative areas and PIN codes

GeoJSON, WGS 84 (EPSG:4326), Polygon or MultiPolygon features.

```bash
python -m scripts.etl.load admin --file districts.geojson --level district --name-field DISTRICT --name-te-field DIST_TE --source-id sources_admin
python -m scripts.etl.load admin --file mandals.geojson   --level mandal   --name-field MANDAL --lgd-field LGD_CODE --source-id sources_admin \
        --gw-category-field CATEGORY --gw-year 2024
python -m scripts.etl.load admin --file villages.geojson  --level village  --name-field VILLAGE --source-id sources_admin
python -m scripts.etl.load admin-link
python -m scripts.etl.load pincodes --file pincodes.csv --source-id india_post
```

- `--name-te-field` is optional. Without it the Telugu UI shows the English name. Add Telugu names if the source has them.
- `--gw-category-field` values are normalised: `safe`, `semi_critical` / `semi-critical`, `critical`,
  `over_exploited` / `overexploited`, `saline`. Anything else is left empty and listed as a warning.
- `pincodes.csv` columns: `pincode, office_name, lat, lon`. The PIN must be 6 digits, `office_name` must not be empty and the
  point must lie inside the state's map bounds. Remove rows without usable coordinates first.

### 3. Geology, soil, aquifer (GeoJSON polygons)

```bash
python -m scripts.etl.load geology --file geology.geojson --source-id gsi_geology --field LITHO --name-field FORMATION
python -m scripts.etl.load soil    --file soil.geojson    --source-id nbss_soil    --field TEXTURE
python -m scripts.etl.load aquifer --file aquifer.geojson --source-id cgwb_naquim  --field AQ_TYPE
```

`--field` names the property holding the raw class text. The loader maps that text to the standard classes with the
`etl.*_aliases` tables in `backend/config/states/telangana.yaml` ("contains" match, case-insensitive, **longest
matching key wins**, so "Clay loam" maps to `clay_loam`, not `loam`). Features whose text matches no alias are
**rejected**, not guessed. Either add an alias after thinking about what the class really is, or pass
`--allow-unmapped` to skip them (they are listed, and those areas then have no data for that factor).

Use `--replace` to delete earlier rows from the same source before loading a newer version.

### 4. Terrain, drainage and lineament grid (derived offline)

The app does not process a DEM at run time. You derive a small table of grid cells once, offline, with GIS tools,
and load it. Columns (`lon` and `lat` are the cell centre in WGS 84):

```
lon,lat,res_m,elevation_m,slope_deg,tpi_m,drainage_density,lineament_density
78.4000,17.4000,1000,512.3,1.8,-2.4,1.3,0.9
```

Empty values stay `NULL`. Suggested derivation (any equivalent method is fine; **write down what you did in the
source `--notes`**, because the scoring tables were written for these units):

| Column | Unit | How |
|---|---|---|
| `elevation_m` | m | Mean DEM value in the cell. |
| `slope_deg` | degrees | `gdaldem slope` on a DEM reprojected to a metric CRS (e.g. UTM 44N, EPSG:32644, or an India-wide projected CRS), then the mean per cell. A slope computed on a lon/lat DEM without a scale factor is wrong. |
| `tpi_m` | m | Cell elevation minus the mean elevation in a surrounding neighbourhood (WhiteboxTools `DiffFromMeanElev`, or `gdaldem TPI` for a very local version). The config does not fix a radius; the score table (`-20 m` very favourable to `+50 m` unfavourable) reads naturally for a neighbourhood of about a kilometre. If you use something very different, re-calibrate that table. |
| `drainage_density` | km of stream per km² | Stream network from the DEM (fill depressions, flow accumulation, threshold) or from an official stream layer; sum of stream length in the cell divided by cell area. The result depends strongly on the threshold, so keep it fixed and recorded. |
| `lineament_density` | km of lineament per km² | From an official lineament map (GSI, Bhuvan): sum of line length in the cell divided by cell area. Automatic extraction from a hillshade is subjective; if you do it, say so in the notes. Not used for alluvium (porous media), by design. |

Then register the source(s) and load, saying which source each factor came from (this is how the report names its sources):

```bash
python -m scripts.etl.load grid --file grid_1km.csv \
    --source slope=srtm_derived --source topographic_position=srtm_derived \
    --source drainage_density=srtm_derived --source lineament_density=gsi_lineaments
```

Keys are the factor names in the config: `slope`, `topographic_position`, `drainage_density`, `lineament_density`.
`elevation_m` is stored but is not a scored factor.

### 5. Rainfall (IMD gridded)

Put one `.GRD` file per year in a folder (the year must be in the file name, e.g. `Rainfall_ind2019_rfp25.grd`).

```bash
python -m scripts.etl.load rainfall-imd --dir /data/imd --years 1991-2020 --source-id imd_rf25
python -m scripts.etl.load grid-rainfall --source-id imd_rf25 --min-years 30
```

The reader checks the file size against the expected layout (365 or 366 days × 129 × 135 float32 values) and
rejects any file that does not match. **That layout was written from IMD's published description and checked only
against synthetic files; run `--dry-run` on one real file first and compare a known cell with an IMD plot.**
`grid-rainfall` gives each grid cell the mean annual rainfall and its year-to-year variability of the nearest IMD cell
(IMD's native resolution is about 25 km, so neighbouring grid cells share values). Only IMD cells with at least
`--min-years` usable years take part, and you get a warning if even the longest record is shorter than that: a
"normal" from a short period is not a climatological normal, and the data notes should say so.

### 6. Water-level wells

Two CSV files.

`stations.csv`: `station_code, lat, lon` (required) and optional `name, agency, well_type, aquifer_class`
(`well_type`: `dug_well`, `piezometer`, `borewell`, `other`).

`readings.csv`: `station_code, date, depth_to_water_m` (required) and optional `season`
(`pre_monsoon`, `monsoon`, `post_monsoon`, `winter`; derived from the date when absent).

```bash
python -m scripts.etl.load wells --stations stations.csv --readings readings.csv --source-id cgwb_gwl_2025
```

Readings must be **metres below ground level**, not above-sea-level elevations. Negative values (artesian) are
rejected; values over 200 m produce a unit warning.

### 7. Historical borewell records (optional, sensitive)

`borewells.csv`: `lat, lon, depth_ft` (required), plus **either** `outcome` (`dry`, `low`, `moderate`, `good`)
**or** `yield_lpm` together with `--yield-thresholds`. Optional: `drilled_year`, `location_accuracy_m`,
`casing_depth_ft`, `static_water_level_m`, `record_origin`.

```bash
python -m scripts.etl.load borewells --file borewells.csv --source-id tgwd_borewells --record-origin "state records"
# only if the file has yield but no outcome; the thresholds are YOUR classification, the project assumes none:
python -m scripts.etl.load borewells --file borewells.csv --source-id tgwd_borewells --yield-thresholds 'low<60,moderate<180'
```

- `depth_ft` is feet and must be between 20 and 3000, which catches metre/foot mix-ups.
- Records with poor location accuracy (worse than 500 m, the config default) get half weight.
- Individual points are hidden on the public map in production (`SHOW_RECORD_POINTS` is off). They still adjust results
  and the depth range, and only as aggregates.
- Make sure you have the right to use and display derived results from these records.

### 8. Geophysical surveys (optional)

`ves.csv`: `lat, lon, method, suitability` (`good` / `moderate` / `poor`) plus optional `survey_year,
weathered_thickness_m, fracture_zone_top_m, fracture_zone_bottom_m, agency, note`.

```bash
python -m scripts.etl.load ves --file ves.csv --source-id tgwd_ves --agency "State Ground Water Department"
```

`suitability` is the interpreter's conclusion. If your data is raw resistivity curves, someone qualified must
interpret them first; the app does not.

### 9. Coverage and the map layer

```bash
python -m scripts.etl.load coverage --status partial      # coverage area = the cells you loaded
python -m scripts.compute_potential                       # writes the class of every cell
```

Points outside the coverage area are reported as "outside the covered area" with the grey class. Run
`compute_potential` again after any change to water-level data, grid data or `telangana.yaml`.

## Switching the running app from demo to production

1. Load everything above. Demo rows may stay in the database: the API reads only the rows that match its mode, so
   they cannot reach a production analysis.
2. Set `APP_DATA_MODE=production` and restart the API. The web app then shows no demonstration banner, and the
   report never carries the demonstration label. In production mode the API refuses the in-memory backend.
3. Check `/api/datasets`: every listed source should be one you registered, with the licence and dates you expect.
4. Read `docs/METHODOLOGY.md`, "Before real people rely on this" first. The score tables are priors, not fitted.

## Adding another state

1. Copy `backend/config/states/telangana.yaml` to `<state>.yaml`; change `state:` (code, names, `map_bounds`).
2. Review **every** table: lithology, aquifer and soil classes and their scores, alias maps, the hard-rock list,
   rainfall and water-level breakpoints. A scoring table that is right for the Deccan plateau can be wrong on the
   Gangetic alluvium or in the Himalaya. Have a hydrogeologist who knows that state review it.
3. Run the loaders with `--state <state>` and `APP_STATE=<state>`.
4. Add the state's Telugu/Hindi/other-language names. The UI currently has English and Telugu only; other languages
   mean a new file next to `frontend/src/i18n/te.js` (same keys) and the same `{lang: text}` shape in the API texts.
