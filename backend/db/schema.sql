-- =============================================================================
-- Borewell Water Finder - PostgreSQL / PostGIS schema
-- =============================================================================
-- Design rules
--   * Every spatial/data row points to a row in `data_sources` (provenance).
--   * Every data table has `is_demo`. The API runs in exactly one mode:
--       APP_DATA_MODE=demo        -> reads ONLY rows with is_demo = true
--       APP_DATA_MODE=production  -> reads ONLY rows with is_demo = false
--     so synthetic demonstration rows can never leak into a real analysis.
--   * All geometries are EPSG:4326 (WGS 84, lon/lat).
--   * New states are added by inserting a `states` row and loading data with
--     that state_code; no schema change is needed.
-- Run once:  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- -----------------------------------------------------------------------------
-- Provenance
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_sources (
    source_id         text PRIMARY KEY,                 -- e.g. 'cgwb_gwl_2025', 'demo_geology'
    name_en           text NOT NULL,
    name_te           text,
    publisher         text NOT NULL,                    -- e.g. 'Central Ground Water Board'
    layer_kind        text NOT NULL CHECK (layer_kind IN (
                        'admin','pincode','geology','soil','aquifer','terrain','drainage',
                        'lineament','rainfall','water_level','borewell','geophysics',
                        'gw_assessment','other')),
    url               text,
    license           text,
    version           text,
    retrieved_on      date,                             -- when WE downloaded it
    data_last_updated date,                             -- newest observation / publication date
    is_demo           boolean NOT NULL DEFAULT false,
    notes             text
);

-- -----------------------------------------------------------------------------
-- States and administrative hierarchy
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS states (
    state_code        text PRIMARY KEY,                 -- 'TG'
    name_en           text NOT NULL,
    name_te           text,
    coverage_status   text NOT NULL DEFAULT 'planned'
                        CHECK (coverage_status IN ('planned','partial','active','demo')),
    coverage_geom     geometry(MultiPolygon, 4326),     -- where we hold enough data to analyse
    config_key        text NOT NULL                     -- file name under config/states/
);

CREATE TABLE IF NOT EXISTS admin_areas (
    area_id           bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    level             text NOT NULL CHECK (level IN ('district','mandal','village')),
    parent_id         bigint REFERENCES admin_areas(area_id),
    lgd_code          text,                             -- Local Government Directory code
    name_en           text NOT NULL,
    name_te           text,
    centroid          geometry(Point, 4326) NOT NULL,
    geom              geometry(MultiPolygon, 4326),     -- NULL when only a gazetteer point is known
    gw_category       text CHECK (gw_category IN ('safe','semi_critical','critical','over_exploited','saline')),
    gw_category_year  smallint,                         -- CGWB/State dynamic resource assessment year
    source_id         text REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS admin_areas_centroid_gix ON admin_areas USING gist (centroid);
CREATE INDEX IF NOT EXISTS admin_areas_geom_gix     ON admin_areas USING gist (geom);
CREATE INDEX IF NOT EXISTS admin_areas_parent_ix    ON admin_areas (level, parent_id);
CREATE INDEX IF NOT EXISTS admin_areas_name_en_trgm ON admin_areas USING gin (name_en gin_trgm_ops);
CREATE INDEX IF NOT EXISTS admin_areas_name_te_trgm ON admin_areas USING gin (name_te gin_trgm_ops);

CREATE TABLE IF NOT EXISTS pincodes (
    pincode           char(6) NOT NULL CHECK (pincode ~ '^[1-9][0-9]{5}$'),
    office_name       text NOT NULL,
    state_code        text NOT NULL REFERENCES states(state_code),
    district_area_id  bigint REFERENCES admin_areas(area_id),
    centroid          geometry(Point, 4326) NOT NULL,
    source_id         text REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false,
    PRIMARY KEY (pincode, office_name)
);
CREATE INDEX IF NOT EXISTS pincodes_centroid_gix ON pincodes USING gist (centroid);

-- -----------------------------------------------------------------------------
-- Thematic polygon layers (standardised classes; see config/states/*.yaml)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS geology_units (
    gid               bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    lithology_class   text NOT NULL,                    -- standard class key
    formation_name    text,                             -- original name as published
    age               text,
    geom              geometry(MultiPolygon, 4326) NOT NULL,
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS geology_units_gix ON geology_units USING gist (geom);

CREATE TABLE IF NOT EXISTS soil_units (
    gid               bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    soil_class        text NOT NULL,
    soil_name         text,
    geom              geometry(MultiPolygon, 4326) NOT NULL,
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS soil_units_gix ON soil_units USING gist (geom);

CREATE TABLE IF NOT EXISTS aquifer_units (
    gid               bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    aquifer_class     text NOT NULL,
    aquifer_name      text,
    typical_yield_lps_min numeric(6,2),                 -- as published (litres/second), optional
    typical_yield_lps_max numeric(6,2),
    geom              geometry(MultiPolygon, 4326) NOT NULL,
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS aquifer_units_gix ON aquifer_units USING gist (geom);

-- -----------------------------------------------------------------------------
-- Terrain / drainage / lineament / rainfall features on a regular grid.
-- Derived offline from DEM (SRTM / Cartosat / NASADEM), drainage network,
-- lineament interpretation and the IMD rainfall series. One row per cell.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_grid (
    cell_id           bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    res_m             integer NOT NULL,                 -- nominal cell size in metres
    geom              geometry(Polygon, 4326) NOT NULL,
    centroid          geometry(Point, 4326) NOT NULL,
    elevation_m       real,
    slope_deg         real,
    tpi_m             real,                             -- elevation minus mean of surroundings
    drainage_density  real,                             -- km / km2
    lineament_density real,                             -- km / km2
    rainfall_normal_mm real,                            -- long-period mean annual rainfall
    rainfall_cv       real,                             -- coefficient of variation (%)
    source_ids        jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {"slope": "<source_id>", ...}
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS feature_grid_gix ON feature_grid USING gist (geom);
CREATE INDEX IF NOT EXISTS feature_grid_cix ON feature_grid USING gist (centroid);

-- Pre-computed regional potential (written by scripts/compute_potential.py).
CREATE TABLE IF NOT EXISTS potential_cells (
    cell_id           bigint PRIMARY KEY REFERENCES feature_grid(cell_id) ON DELETE CASCADE,
    regional_score    real,                             -- NULL => insufficient data
    regional_class    text NOT NULL,
    coverage          real NOT NULL,
    factor_scores     jsonb NOT NULL DEFAULT '{}'::jsonb,
    method_version    text NOT NULL,
    computed_at       timestamptz NOT NULL DEFAULT now(),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS potential_cells_class_ix ON potential_cells (regional_class);

-- -----------------------------------------------------------------------------
-- Rainfall records (IMD gridded 0.25 deg series, or station data)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rainfall_cells (
    cell_key          text PRIMARY KEY,                 -- e.g. 'imd025_78.25_17.50'
    geom              geometry(Point, 4326) NOT NULL,
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS rainfall_cells_gix ON rainfall_cells USING gist (geom);

CREATE TABLE IF NOT EXISTS rainfall_annual (
    cell_key          text NOT NULL REFERENCES rainfall_cells(cell_key) ON DELETE CASCADE,
    year              smallint NOT NULL,
    annual_mm         real NOT NULL,
    monsoon_mm        real,                             -- Jun-Sep total
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false,
    PRIMARY KEY (cell_key, year)
);

-- -----------------------------------------------------------------------------
-- Groundwater monitoring wells (CGWB National Hydrograph Stations + State GWD)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS observation_wells (
    well_id           bigserial PRIMARY KEY,
    station_code      text NOT NULL UNIQUE,
    name              text,
    state_code        text NOT NULL REFERENCES states(state_code),
    well_type         text CHECK (well_type IN ('dug_well','piezometer','borewell','other')),
    agency            text,                             -- 'CGWB' | 'SGWD' | ...
    aquifer_class     text,
    geom              geometry(Point, 4326) NOT NULL,
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS observation_wells_gix ON observation_wells USING gist (geom);

CREATE TABLE IF NOT EXISTS water_level_readings (
    reading_id        bigserial PRIMARY KEY,
    well_id           bigint NOT NULL REFERENCES observation_wells(well_id) ON DELETE CASCADE,
    measured_on       date NOT NULL,
    season            text NOT NULL CHECK (season IN ('pre_monsoon','monsoon','post_monsoon','winter')),
    depth_to_water_m  numeric(6,2) NOT NULL CHECK (depth_to_water_m >= 0),   -- metres below ground level
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false,
    UNIQUE (well_id, measured_on)
);
CREATE INDEX IF NOT EXISTS water_level_readings_well_ix ON water_level_readings (well_id, measured_on DESC);

-- -----------------------------------------------------------------------------
-- Historical borewell records (exploration / departmental inventories)
-- NOTE: private landowner records are sensitive. The API never returns exact
-- coordinates of individual records unless SHOW_RECORD_POINTS=true.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS borewell_records (
    borewell_id       bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    geom              geometry(Point, 4326) NOT NULL,
    location_accuracy_m integer,                        -- NULL = unknown
    drilled_year      smallint,
    depth_ft          numeric(7,1) NOT NULL CHECK (depth_ft > 0),
    casing_depth_ft   numeric(7,1),
    yield_lpm         numeric(8,1) CHECK (yield_lpm >= 0),   -- litres per minute; 0 = dry
    static_water_level_m numeric(6,2),
    outcome           text NOT NULL CHECK (outcome IN ('dry','low','moderate','good')),
    record_origin     text,                             -- 'CGWB_exploration' | 'SGWD' | 'PHED' | ...
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS borewell_records_gix ON borewell_records USING gist (geom);

-- -----------------------------------------------------------------------------
-- Geophysical surveys (Vertical Electrical Sounding / Electrical Resistivity Tomography)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS geophysical_surveys (
    survey_id         bigserial PRIMARY KEY,
    state_code        text NOT NULL REFERENCES states(state_code),
    geom              geometry(Point, 4326) NOT NULL,
    method            text NOT NULL,                    -- 'VES-Schlumberger' | 'ERT' | ...
    survey_year       smallint,
    weathered_thickness_m numeric(6,1),
    fracture_zone_top_m   numeric(6,1),
    fracture_zone_bottom_m numeric(6,1),
    interpreted_suitability text NOT NULL CHECK (interpreted_suitability IN ('good','moderate','poor')),
    interpretation_note text,
    agency            text,
    source_id         text NOT NULL REFERENCES data_sources(source_id),
    is_demo           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS geophysical_surveys_gix ON geophysical_surveys USING gist (geom);

-- -----------------------------------------------------------------------------
-- Contact form (minimal personal data; purge periodically)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contact_messages (
    message_id        bigserial PRIMARY KEY,
    name              text NOT NULL,
    email             text,
    phone             text,
    message           text NOT NULL,
    lang              text,
    created_at        timestamptz NOT NULL DEFAULT now()
);


-- -----------------------------------------------------------------------------
-- NWIC Telangana six-hourly telemetry (separate from daily historical readings)
-- Store the publisher's numeric value unchanged until its sign/measurement
-- convention is independently verified. This table is not synthetic/demo data.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS groundwater_telemetry_stations (
    station_code text PRIMARY KEY,
    station_name text NOT NULL,
    district text,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    agency text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS groundwater_telemetry_stations_district_ix
    ON groundwater_telemetry_stations (district);

CREATE TABLE IF NOT EXISTS groundwater_telemetry_readings (
    telemetry_id bigserial PRIMARY KEY,
    station_code text NOT NULL REFERENCES groundwater_telemetry_stations(station_code) ON DELETE CASCADE,
    observed_at timestamptz NOT NULL,
    level_value_m double precision NOT NULL,
    source_record_id text,
    imported_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (station_code, observed_at)
);
CREATE INDEX IF NOT EXISTS groundwater_telemetry_readings_latest_ix
    ON groundwater_telemetry_readings (station_code, observed_at DESC);
