"""Load REAL datasets into PostgreSQL/PostGIS (always is_demo = false).

    python -m scripts.etl.load <command> [options]

Nothing is downloaded here: the official portals (CGWB, India-WRIS, GSI Bhukosh, Bhuvan, IMD, the State
groundwater department) need manual download and/or acceptance of licence terms. Download first, then load
the files with the commands below; see docs/DATA_INTEGRATION.md for where each file comes from and its columns.

Commands (run in this order):
    state          create/update the state row
    source         register a dataset (publisher, licence, dates)  - needed before loading its data
    admin          district / mandal / village polygons (GeoJSON)    + admin-link, pincodes
    geology | soil | aquifer   thematic polygons (GeoJSON, WGS84), classes mapped with config etl.*_aliases
    grid           terrain/drainage/lineament cells (CSV, derived offline from the DEM)
    rainfall-imd   IMD 0.25 deg .GRD files -> rainfall_cells/rainfall_annual ; grid-rainfall copies the normal to the grid
    wells          groundwater monitoring stations + water-level readings (CSV)
    borewells      historical borewell records (CSV)           ves   geophysical surveys (CSV)
    coverage       set the state's coverage area = union of loaded grid cells
Then:  python -m scripts.compute_potential   and, once there are >= 500 real borewell records, scripts.train_model.

Every command validates first, prints a summary, and loads nothing if any row is invalid unless --skip-invalid.
Use --dry-run to validate and roll back.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from app.engine import load_state_config
from app.engine.config import StateConfig

from .imd import NLAT, NLON, LAT0, LON0, STEP, annual_totals, cell_key, read_grd
from .mapping import (OUTCOMES, Report, check_latlon, map_alias, opt_num, outcome_from_yield, parse_date,
                      parse_thresholds, read_csv, req_num, season_for)

KINDS = ("admin", "pincode", "geology", "soil", "aquifer", "terrain", "drainage", "lineament", "rainfall",
         "water_level", "borewell", "geophysics", "gw_assessment", "other")
GW_CATEGORIES = {"safe", "semi_critical", "critical", "over_exploited", "saline"}


class Db:
    """Thin psycopg wrapper. Tests substitute a recording object with the same three methods."""

    def __init__(self, url: str):
        import psycopg
        self.conn = psycopg.connect(url)

    def execute(self, sql: str, params=None):
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, rows) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()


def _finish(db, report: Report, *, dry_run: bool, skip_invalid: bool, what: str) -> bool:
    print(f"{what}: {report.summary()}")
    for w in report.warnings[:10]:
        print("  warning:", w)
    if report.errors and not skip_invalid:
        db.rollback()
        print("nothing loaded (fix the rows above, or pass --skip-invalid to load only the valid ones)")
        return False
    if dry_run:
        db.rollback()
        print("dry run: rolled back")
    else:
        db.commit()
        print("committed")
    return True


# --------------------------------------------------------------------------- state / source
def cmd_state(db, cfg: StateConfig, *, config_key: str, status: str = "planned") -> Report:
    db.execute("""INSERT INTO states (state_code, name_en, name_te, coverage_status, config_key)
                  VALUES (%s, %s, %s, %s, %s)
                  ON CONFLICT (state_code) DO UPDATE SET name_en = EXCLUDED.name_en, name_te = EXCLUDED.name_te,
                                                         config_key = EXCLUDED.config_key""",
               (cfg.code, cfg.name["en"], cfg.name["te"], status, config_key))
    return Report(ok=1)


def cmd_source(db, *, source_id: str, name_en: str, publisher: str, kind: str, license: str, last_updated: date,
               retrieved_on: Optional[date] = None, url: Optional[str] = None, version: Optional[str] = None,
               name_te: Optional[str] = None, notes: Optional[str] = None) -> Report:
    rep = Report()
    if kind not in KINDS:
        rep.err(0, f"kind must be one of {KINDS}")
    if source_id.lower().startswith("demo") or name_en.lower().startswith("demo"):
        rep.err(0, "ids/names starting with 'demo' are reserved for synthetic data")
    if last_updated > date.today():
        rep.err(0, "last_updated is in the future")
    if rep.errors:
        return rep
    db.execute("""INSERT INTO data_sources (source_id, name_en, name_te, publisher, layer_kind, url, license, version,
                                            retrieved_on, data_last_updated, is_demo, notes)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,%s)
                  ON CONFLICT (source_id) DO UPDATE SET name_en=EXCLUDED.name_en, name_te=EXCLUDED.name_te,
                      publisher=EXCLUDED.publisher, layer_kind=EXCLUDED.layer_kind, url=EXCLUDED.url,
                      license=EXCLUDED.license, version=EXCLUDED.version, retrieved_on=EXCLUDED.retrieved_on,
                      data_last_updated=EXCLUDED.data_last_updated, is_demo=false, notes=EXCLUDED.notes""",
               (source_id, name_en, name_te, publisher, kind, url, license, version,
                retrieved_on or date.today(), last_updated, notes))
    rep.ok = 1
    return rep


def _require_source(db, source_id: str, rep: Report) -> bool:
    row = db.execute("SELECT is_demo FROM data_sources WHERE source_id = %s", (source_id,)).fetchone()
    if row is None:
        rep.err(0, f"source '{source_id}' is not registered - run the `source` command first")
        return False
    if row[0]:
        rep.err(0, f"source '{source_id}' is a demo source; real data must use a real source record")
        return False
    return True


# --------------------------------------------------------------------------- GeoJSON polygon layers
POLY_TABLES = {
    "geology": ("geology_units", "lithology_class", "formation_name", "lithology_aliases"),
    "soil": ("soil_units", "soil_class", "soil_name", "soil_aliases"),
    "aquifer": ("aquifer_units", "aquifer_class", "aquifer_name", "aquifer_aliases"),
}


def _read_geojson(path: str) -> list[dict]:
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    crs = (gj.get("crs") or {}).get("properties", {}).get("name", "")
    if crs and not re.search(r"(CRS84|EPSG::?4326)$", crs):
        raise ValueError(f"GeoJSON CRS is {crs}; reproject to WGS84 first (ogr2ogr -t_srs EPSG:4326)")
    if gj.get("type") != "FeatureCollection":
        raise ValueError("expected a GeoJSON FeatureCollection")
    return gj["features"]


def _first_coord(geom: dict):
    c = geom["coordinates"]
    while isinstance(c[0], (list, tuple)):
        c = c[0]
    return c


def cmd_polygons(db, cfg: StateConfig, *, layer: str, path: str, source_id: str, field: str,
                 name_field: Optional[str] = None, age_field: Optional[str] = None, replace: bool = False,
                 allow_unmapped: bool = False) -> Report:
    table, class_col, name_col, alias_key = POLY_TABLES[layer]
    aliases = cfg.section("etl")[alias_key]
    valid_classes = set(aliases.values())
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    unmapped: dict[str, int] = {}
    rows = []
    for i, f in enumerate(_read_geojson(path), start=1):
        props, geom = f.get("properties") or {}, f.get("geometry")
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            rep.err(i, "geometry is not a Polygon/MultiPolygon")
            continue
        raw = props.get(field)
        cls = map_alias(raw, aliases)
        if cls is None:
            unmapped[str(raw)] = unmapped.get(str(raw), 0) + 1
            continue
        assert cls in valid_classes
        lon, lat = _first_coord(geom)[:2]
        try:
            check_latlon(lat, lon, cfg.map_bounds)
        except ValueError as e:
            rep.err(i, str(e))
            continue
        row = [cfg.code, cls, props.get(name_field) if name_field else raw]
        if layer == "geology":
            row.append(props.get(age_field) if age_field else None)
        rows.append(tuple(row) + (json.dumps(geom), source_id))
    for raw, n in sorted(unmapped.items(), key=lambda x: -x[1]):
        msg = f"{n} feature(s) with unmapped class {raw!r} - add a matching key to etl.{alias_key} in the state config"
        (rep.warnings if allow_unmapped else rep.errors).append(msg)
    if rep.errors:
        return rep
    if replace:
        db.execute(f"DELETE FROM {table} WHERE state_code = %s AND source_id = %s AND is_demo = false", (cfg.code, source_id))
    age_col, age_ph = (", age", ", %s") if layer == "geology" else ("", "")
    db.executemany(
        f"INSERT INTO {table} (state_code, {class_col}, {name_col}{age_col}, geom, source_id, is_demo) "
        f"VALUES (%s, %s, %s{age_ph}, ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3)), %s, false)",
        rows)
    rep.ok = len(rows)
    return rep


# --------------------------------------------------------------------------- administrative areas & PIN codes
def _gw_cat(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    k = re.sub(r"[\s\-]+", "_", raw.strip().lower())
    k = {"overexploited": "over_exploited", "over_exploited": "over_exploited", "semicritical": "semi_critical"}.get(k, k)
    return k if k in GW_CATEGORIES else None


def cmd_admin(db, cfg: StateConfig, *, path: str, level: str, name_field: str, name_te_field: Optional[str] = None,
              lgd_field: Optional[str] = None, source_id: Optional[str] = None, gw_category_field: Optional[str] = None,
              gw_year: Optional[int] = None) -> Report:
    rep = Report()
    if source_id and not _require_source(db, source_id, rep):
        return rep
    rows = []
    for i, f in enumerate(_read_geojson(path), start=1):
        p, geom = f.get("properties") or {}, f.get("geometry")
        name = (p.get(name_field) or "").strip()
        if not name or not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            rep.err(i, "missing name or polygon geometry")
            continue
        cat = _gw_cat(p.get(gw_category_field)) if gw_category_field else None
        if gw_category_field and p.get(gw_category_field) and cat is None:
            rep.warnings.append(f"feature {i}: groundwater category {p.get(gw_category_field)!r} not recognised; left empty")
        rows.append((cfg.code, level, p.get(lgd_field) if lgd_field else None, name,
                     (p.get(name_te_field) or None) if name_te_field else None, json.dumps(geom), cat,
                     gw_year if cat else None, source_id))
    if rep.errors:
        return rep
    db.executemany("""INSERT INTO admin_areas (state_code, level, lgd_code, name_en, name_te, geom, centroid,
                                               gw_category, gw_category_year, source_id, is_demo)
                      SELECT %s, %s, %s, %s, %s, g.geom, ST_PointOnSurface(g.geom), %s, %s, %s, false
                      FROM (SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3)) AS geom) g""",
                   [(r[0], r[1], r[2], r[3], r[4], r[6], r[7], r[8], r[5]) for r in rows])
    rep.ok = len(rows)
    return rep


def cmd_admin_link(db, cfg: StateConfig) -> Report:
    """Set parent_id from spatial containment: village -> mandal -> district; PIN codes -> district."""
    for child, parent in (("mandal", "district"), ("village", "mandal")):
        db.execute("""UPDATE admin_areas c SET parent_id = p.area_id
                      FROM admin_areas p
                      WHERE c.state_code = %s AND c.is_demo = false AND c.level = %s AND c.parent_id IS NULL
                        AND p.state_code = c.state_code AND p.is_demo = false AND p.level = %s
                        AND ST_Contains(p.geom, c.centroid)""", (cfg.code, child, parent))
    db.execute("""UPDATE pincodes pc SET district_area_id = a.area_id
                  FROM admin_areas a
                  WHERE pc.state_code = %s AND pc.is_demo = false AND a.state_code = pc.state_code AND a.is_demo = false
                    AND a.level = 'district' AND ST_Contains(a.geom, pc.centroid)""", (cfg.code,))
    return Report(ok=1)


def cmd_pincodes(db, cfg: StateConfig, *, path: str, source_id: str) -> Report:
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    rows = []
    for n, r in read_csv(path, ["pincode", "office_name", "lat", "lon"]):
        try:
            if not re.fullmatch(r"[1-9][0-9]{5}", r["pincode"]):
                raise ValueError("PIN code must be 6 digits")
            lat, lon = req_num(r["lat"], "lat"), req_num(r["lon"], "lon")
            check_latlon(lat, lon, cfg.map_bounds)
            if not r["office_name"]:
                raise ValueError("office_name is empty")
            rows.append((r["pincode"], r["office_name"], cfg.code, lon, lat, source_id))
        except ValueError as e:
            rep.err(n, str(e))
    if rep.errors:
        return rep
    db.executemany("""INSERT INTO pincodes (pincode, office_name, state_code, centroid, source_id, is_demo)
                      VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, false)
                      ON CONFLICT (pincode, office_name) DO UPDATE SET centroid = EXCLUDED.centroid,
                                                                       source_id = EXCLUDED.source_id, is_demo = false""", rows)
    rep.ok = len(rows)
    return rep


# --------------------------------------------------------------------------- feature grid
def cmd_grid(db, cfg: StateConfig, *, path: str, source_map: dict[str, str], replace: bool = False) -> Report:
    """CSV columns: lon, lat (cell centre), res_m, elevation_m, slope_deg, tpi_m, drainage_density, lineament_density.
    Empty values stay NULL (and the factor is then reported as 'no data' - never filled in)."""
    rep = Report()
    for k in source_map:
        if k not in cfg.factors:
            rep.err(0, f"--source key {k!r} is not a factor of this state ({sorted(cfg.factors)})")
    for sid in set(source_map.values()):
        _require_source(db, sid, rep)
    if rep.errors:
        return rep
    rows = []
    for n, r in read_csv(path, ["lon", "lat", "res_m"]):
        try:
            lon, lat, res = req_num(r["lon"], "lon"), req_num(r["lat"], "lat"), req_num(r["res_m"], "res_m")
            check_latlon(lat, lon, cfg.map_bounds)
            if not 10 <= res <= 10000:
                raise ValueError("res_m should be between 10 and 10000")
            vals = {k: opt_num(r.get(k), k) for k in ("elevation_m", "slope_deg", "tpi_m", "drainage_density", "lineament_density")}
            if vals["slope_deg"] is not None and not 0 <= vals["slope_deg"] <= 90:
                raise ValueError("slope_deg outside 0-90")
            if any(v is not None and v < 0 for k, v in vals.items() if k in ("drainage_density", "lineament_density")):
                raise ValueError("densities cannot be negative")
            dlat = res / 2.0 / 111_195.0
            dlon = dlat / max(0.2, math.cos(math.radians(lat)))
            rows.append((cfg.code, int(res), lon - dlon, lat - dlat, lon + dlon, lat + dlat, lon, lat,
                         vals["elevation_m"], vals["slope_deg"], vals["tpi_m"], vals["drainage_density"],
                         vals["lineament_density"], json.dumps(source_map)))
        except ValueError as e:
            rep.err(n, str(e))
    if rep.errors:
        return rep
    if replace:
        db.execute("DELETE FROM feature_grid WHERE state_code = %s AND is_demo = false", (cfg.code,))
    db.executemany("""INSERT INTO feature_grid (state_code, res_m, geom, centroid, elevation_m, slope_deg, tpi_m,
                                                drainage_density, lineament_density, source_ids, is_demo)
                      VALUES (%s, %s, ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                              %s, %s, %s, %s, %s, %s::jsonb, false)""", rows)
    rep.ok = len(rows)
    return rep


# --------------------------------------------------------------------------- rainfall (IMD)
def cmd_rainfall_imd(db, cfg: StateConfig, *, directory: str, years: range, source_id: str, margin_deg: float = 0.5) -> Report:
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    (s, w), (n, e) = cfg.map_bounds
    lats = [LAT0 + STEP * i for i in range(NLAT)]
    lons = [LON0 + STEP * j for j in range(NLON)]
    ii = [i for i, la in enumerate(lats) if s - margin_deg <= la <= n + margin_deg]
    jj = [j for j, lo in enumerate(lons) if w - margin_deg <= lo <= e + margin_deg]
    files = {p.name.lower(): p for p in Path(directory).iterdir() if p.suffix.lower() == ".grd"}
    cells_done = set()
    for year in years:
        match = [p for name, p in files.items() if str(year) in name]
        if len(match) != 1:
            rep.err(0, f"year {year}: expected exactly one .grd file containing '{year}' in {directory}, found {len(match)}")
            continue
        try:
            ann, mon = annual_totals(read_grd(match[0], year), year)
        except ValueError as ex:
            rep.err(0, str(ex))
            continue
        batch = []
        for i in ii:
            for j in jj:
                if math.isnan(ann[i, j]):
                    continue
                key = cell_key(lons[j], lats[i])
                if key not in cells_done:
                    db.execute("""INSERT INTO rainfall_cells (cell_key, geom, is_demo)
                                  VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), false) ON CONFLICT (cell_key) DO NOTHING""",
                               (key, lons[j], lats[i]))
                    cells_done.add(key)
                batch.append((key, year, float(ann[i, j]), None if math.isnan(mon[i, j]) else float(mon[i, j]), source_id))
        db.executemany("""INSERT INTO rainfall_annual (cell_key, year, annual_mm, monsoon_mm, source_id, is_demo)
                          VALUES (%s, %s, %s, %s, %s, false)
                          ON CONFLICT (cell_key, year) DO UPDATE SET annual_mm = EXCLUDED.annual_mm,
                              monsoon_mm = EXCLUDED.monsoon_mm, source_id = EXCLUDED.source_id, is_demo = false""", batch)
        rep.ok += len(batch)
    return rep


def cmd_grid_rainfall(db, cfg: StateConfig, *, min_years: int, source_id: str) -> Report:
    """Copy the long-period mean and CV of the NEAREST IMD cell to each grid cell (native resolution is ~25 km)."""
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    row = db.execute("SELECT max(c) FROM (SELECT count(*) c FROM rainfall_annual WHERE is_demo = false GROUP BY cell_key) t").fetchone()
    longest = (row[0] if row else 0) or 0
    if longest < min_years:
        rep.warnings.append(f"only {longest} years of rainfall are loaded (< {min_years}); the 'normal' is a short-period mean - "
                            "say so in the data notes")
    db.execute("""WITH stats AS (
                    SELECT cell_key, avg(annual_mm) AS mean_mm, 100.0 * stddev_samp(annual_mm) / NULLIF(avg(annual_mm), 0) AS cv
                    FROM rainfall_annual WHERE is_demo = false GROUP BY cell_key HAVING count(*) >= %s)
                  UPDATE feature_grid g
                  SET rainfall_normal_mm = (SELECT s.mean_mm FROM rainfall_cells c JOIN stats s USING (cell_key)
                                            WHERE c.is_demo = false ORDER BY c.geom <-> g.centroid LIMIT 1),
                      rainfall_cv = (SELECT s.cv FROM rainfall_cells c JOIN stats s USING (cell_key)
                                     WHERE c.is_demo = false ORDER BY c.geom <-> g.centroid LIMIT 1),
                      source_ids = g.source_ids || jsonb_build_object('rainfall', %s::text)
                  WHERE g.state_code = %s AND g.is_demo = false""", (min_years, source_id, cfg.code))
    rep.ok = 1
    return rep


# --------------------------------------------------------------------------- wells, borewells, geophysics
def cmd_wells(db, cfg: StateConfig, *, stations: str, readings: str, source_id: str, agency: Optional[str] = None) -> Report:
    """stations CSV: station_code,name,lat,lon[,agency,well_type,aquifer_class]; readings CSV: station_code,date,depth_to_water_m[,season]."""
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    st_rows, known = [], set()
    for n, r in read_csv(stations, ["station_code", "lat", "lon"]):
        try:
            lat, lon = req_num(r["lat"], "lat"), req_num(r["lon"], "lon")
            check_latlon(lat, lon, cfg.map_bounds)
            wt = r.get("well_type") or None
            if wt not in (None, "dug_well", "piezometer", "borewell", "other"):
                raise ValueError("well_type must be dug_well, piezometer, borewell or other")
            if not r["station_code"]:
                raise ValueError("station_code is empty")
            known.add(r["station_code"])
            st_rows.append((r["station_code"], r.get("name") or None, cfg.code, wt, r.get("agency") or agency,
                            r.get("aquifer_class") or None, lon, lat, source_id))
        except ValueError as e:
            rep.err(n, f"stations: {e}")
    rd_rows = []
    for n, r in read_csv(readings, ["station_code", "date", "depth_to_water_m"]):
        try:
            if r["station_code"] not in known:
                raise ValueError(f"station {r['station_code']!r} is not in the stations file")
            d = parse_date(r["date"])
            if d > date.today():
                raise ValueError("date is in the future")
            depth = req_num(r["depth_to_water_m"], "depth_to_water_m")
            if depth < 0:
                raise ValueError("depth_to_water_m is negative (artesian/above-ground readings are not supported)")
            if depth > 200:
                rep.warnings.append(f"readings row {n}: depth {depth} m is unusually deep - check units (metres below ground level)")
            season = r.get("season") or season_for(d)
            if season not in ("pre_monsoon", "monsoon", "post_monsoon", "winter"):
                raise ValueError(f"season {season!r} not recognised")
            rd_rows.append((r["station_code"], d, season, depth, source_id))
        except ValueError as e:
            rep.err(n, f"readings: {e}")
    if rep.errors:
        return rep
    db.executemany("""INSERT INTO observation_wells (station_code, name, state_code, well_type, agency, aquifer_class, geom, source_id, is_demo)
                      VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, false)
                      ON CONFLICT (station_code) DO UPDATE SET name = EXCLUDED.name, well_type = EXCLUDED.well_type,
                          agency = EXCLUDED.agency, aquifer_class = EXCLUDED.aquifer_class, geom = EXCLUDED.geom,
                          source_id = EXCLUDED.source_id, is_demo = false""", st_rows)
    db.executemany("""INSERT INTO water_level_readings (well_id, measured_on, season, depth_to_water_m, source_id, is_demo)
                      SELECT w.well_id, %s, %s, %s, %s, false FROM observation_wells w WHERE w.station_code = %s
                      ON CONFLICT (well_id, measured_on) DO UPDATE SET depth_to_water_m = EXCLUDED.depth_to_water_m,
                          season = EXCLUDED.season, source_id = EXCLUDED.source_id, is_demo = false""",
                   [(d, s, v, sid, code) for code, d, s, v, sid in rd_rows])
    rep.ok = len(st_rows) + len(rd_rows)
    return rep


def cmd_borewells(db, cfg: StateConfig, *, path: str, source_id: str, record_origin: Optional[str] = None,
                  yield_thresholds: Optional[str] = None) -> Report:
    """CSV: lat,lon,depth_ft and either outcome (dry|low|moderate|good) or yield_lpm (+ --yield-thresholds);
    optional drilled_year, location_accuracy_m, casing_depth_ft, static_water_level_m, record_origin.
    No owner names, phone numbers or survey numbers are accepted or stored."""
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    thr = parse_thresholds(yield_thresholds) if yield_thresholds else None
    rows = []
    for n, r in read_csv(path, ["lat", "lon", "depth_ft"]):
        try:
            lat, lon, depth = req_num(r["lat"], "lat"), req_num(r["lon"], "lon"), req_num(r["depth_ft"], "depth_ft")
            check_latlon(lat, lon, cfg.map_bounds)
            if not 20 <= depth <= 3000:
                raise ValueError("depth_ft outside 20-3000 ft (units?)")
            y = opt_num(r.get("yield_lpm"), "yield_lpm")
            outcome = (r.get("outcome") or "").lower() or None
            if outcome is None:
                if y is None or thr is None:
                    raise ValueError("needs an `outcome` column value, or yield_lpm together with --yield-thresholds")
                outcome = outcome_from_yield(y, thr)
            if outcome not in OUTCOMES:
                raise ValueError(f"outcome must be one of {OUTCOMES}")
            if y is not None and y < 0:
                raise ValueError("yield_lpm is negative")
            year = opt_num(r.get("drilled_year"), "drilled_year")
            if year is not None and not 1900 <= year <= date.today().year:
                raise ValueError("drilled_year out of range")
            acc = opt_num(r.get("location_accuracy_m"), "location_accuracy_m")
            rows.append((cfg.code, lon, lat, None if acc is None else int(acc), None if year is None else int(year), depth,
                         opt_num(r.get("casing_depth_ft"), "casing_depth_ft"), y, opt_num(r.get("static_water_level_m"), "static_water_level_m"),
                         outcome, r.get("record_origin") or record_origin, source_id))
        except ValueError as e:
            rep.err(n, str(e))
    if rep.errors:
        return rep
    db.executemany("""INSERT INTO borewell_records (state_code, geom, location_accuracy_m, drilled_year, depth_ft, casing_depth_ft,
                                                    yield_lpm, static_water_level_m, outcome, record_origin, source_id, is_demo)
                      VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, %s, %s, %s, %s, false)""",
                   [(r[0], r[1], r[2], *r[3:]) for r in rows])
    rep.ok = len(rows)
    return rep


def cmd_ves(db, cfg: StateConfig, *, path: str, source_id: str, agency: Optional[str] = None) -> Report:
    """CSV: lat,lon,method,suitability(good|moderate|poor)[,survey_year,weathered_thickness_m,fracture_zone_top_m,fracture_zone_bottom_m,agency,note]."""
    rep = Report()
    if not _require_source(db, source_id, rep):
        return rep
    rows = []
    for n, r in read_csv(path, ["lat", "lon", "method", "suitability"]):
        try:
            lat, lon = req_num(r["lat"], "lat"), req_num(r["lon"], "lon")
            check_latlon(lat, lon, cfg.map_bounds)
            if r["suitability"].lower() not in ("good", "moderate", "poor"):
                raise ValueError("suitability must be good, moderate or poor")
            if not r["method"]:
                raise ValueError("method is empty")
            yr = opt_num(r.get("survey_year"), "survey_year")
            rows.append((cfg.code, lon, lat, r["method"], None if yr is None else int(yr),
                         opt_num(r.get("weathered_thickness_m"), "weathered_thickness_m"),
                         opt_num(r.get("fracture_zone_top_m"), "fracture_zone_top_m"),
                         opt_num(r.get("fracture_zone_bottom_m"), "fracture_zone_bottom_m"),
                         r["suitability"].lower(), r.get("note") or None, r.get("agency") or agency, source_id))
        except ValueError as e:
            rep.err(n, str(e))
    if rep.errors:
        return rep
    db.executemany("""INSERT INTO geophysical_surveys (state_code, geom, method, survey_year, weathered_thickness_m, fracture_zone_top_m,
                                                       fracture_zone_bottom_m, interpreted_suitability, interpretation_note, agency, source_id, is_demo)
                      VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, %s, %s, %s, %s, false)""",
                   [(r[0], r[1], r[2], *r[3:]) for r in rows])
    rep.ok = len(rows)
    return rep


def cmd_coverage(db, cfg: StateConfig, *, status: str = "partial") -> Report:
    """Coverage = where we hold data = union of the loaded grid cells. Outside it the app says 'outside the covered area'."""
    db.execute("""UPDATE states SET coverage_status = %s,
                         coverage_geom = (SELECT ST_Multi(ST_UnaryUnion(ST_Collect(geom))) FROM feature_grid
                                          WHERE state_code = %s AND is_demo = false)
                  WHERE state_code = %s""", (status, cfg.code, cfg.code))
    return Report(ok=1)


# --------------------------------------------------------------------------- CLI
def _date(v: str) -> date:
    return parse_date(v)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="scripts.etl.load", description=__doc__.split("\n\n")[0])
    ap.add_argument("--state", default=os.environ.get("APP_STATE", "telangana"))
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--dry-run", action="store_true", help="validate and load inside a transaction, then roll back")
    ap.add_argument("--skip-invalid", action="store_true", help="load valid rows even if some rows are rejected")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("state")
    p.add_argument("--status", default="planned", choices=["planned", "partial", "active"])

    p = sub.add_parser("source")
    for a in ("source_id", "name_en", "publisher", "kind", "license"):
        p.add_argument("--" + a.replace("_", "-"), required=True, dest=a)
    p.add_argument("--last-updated", required=True, type=_date, dest="last_updated", help="newest observation/publication date in the data")
    p.add_argument("--retrieved-on", type=_date, dest="retrieved_on")
    for a in ("url", "version", "name_te", "notes"):
        p.add_argument("--" + a.replace("_", "-"), dest=a)

    for layer in POLY_TABLES:
        p = sub.add_parser(layer)
        p.add_argument("--file", required=True)
        p.add_argument("--source-id", required=True)
        p.add_argument("--field", required=True, help="GeoJSON property holding the raw class text")
        p.add_argument("--name-field")
        p.add_argument("--age-field")
        p.add_argument("--replace", action="store_true", help="delete earlier rows from the same source first")
        p.add_argument("--allow-unmapped", action="store_true", help="skip (and report) features whose class cannot be mapped")

    p = sub.add_parser("admin")
    p.add_argument("--file", required=True)
    p.add_argument("--level", required=True, choices=["district", "mandal", "village"])
    p.add_argument("--name-field", required=True)
    p.add_argument("--name-te-field")
    p.add_argument("--lgd-field")
    p.add_argument("--source-id")
    p.add_argument("--gw-category-field")
    p.add_argument("--gw-year", type=int)
    sub.add_parser("admin-link")

    p = sub.add_parser("pincodes")
    p.add_argument("--file", required=True)
    p.add_argument("--source-id", required=True)

    p = sub.add_parser("grid")
    p.add_argument("--file", required=True)
    p.add_argument("--source", action="append", default=[], metavar="FACTOR=SOURCE_ID",
                   help="factor key = registered source id, e.g. --source slope=srtm_2014 --source lineament_density=gsi_2020 (repeatable)")
    p.add_argument("--replace", action="store_true")

    p = sub.add_parser("rainfall-imd")
    p.add_argument("--dir", required=True, dest="directory")
    p.add_argument("--years", required=True, help="e.g. 1991-2020")
    p.add_argument("--source-id", required=True)

    p = sub.add_parser("grid-rainfall")
    p.add_argument("--source-id", required=True)
    p.add_argument("--min-years", type=int, default=30)

    p = sub.add_parser("wells")
    p.add_argument("--stations", required=True)
    p.add_argument("--readings", required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--agency")

    p = sub.add_parser("borewells")
    p.add_argument("--file", required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--record-origin")
    p.add_argument("--yield-thresholds", help="only if the file has yield_lpm but no outcome, e.g. 'low<60,moderate<180' "
                                              "(YOUR classification; the project assumes none)")

    p = sub.add_parser("ves")
    p.add_argument("--file", required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--agency")

    p = sub.add_parser("coverage")
    p.add_argument("--status", default="partial", choices=["partial", "active"])
    return ap


def run(args, db, cfg: StateConfig) -> Report:
    c = args.cmd
    if c == "state":
        return cmd_state(db, cfg, config_key=args.state, status=args.status)
    if c == "source":
        return cmd_source(db, source_id=args.source_id, name_en=args.name_en, publisher=args.publisher, kind=args.kind,
                          license=args.license, last_updated=args.last_updated, retrieved_on=args.retrieved_on,
                          url=args.url, version=args.version, name_te=args.name_te, notes=args.notes)
    if c in POLY_TABLES:
        return cmd_polygons(db, cfg, layer=c, path=args.file, source_id=args.source_id, field=args.field, name_field=args.name_field,
                            age_field=args.age_field, replace=args.replace, allow_unmapped=args.allow_unmapped)
    if c == "admin":
        return cmd_admin(db, cfg, path=args.file, level=args.level, name_field=args.name_field, name_te_field=args.name_te_field,
                         lgd_field=args.lgd_field, source_id=args.source_id, gw_category_field=args.gw_category_field, gw_year=args.gw_year)
    if c == "admin-link":
        return cmd_admin_link(db, cfg)
    if c == "pincodes":
        return cmd_pincodes(db, cfg, path=args.file, source_id=args.source_id)
    if c == "grid":
        sm = dict(s.split("=", 1) for s in args.source)
        return cmd_grid(db, cfg, path=args.file, source_map=sm, replace=args.replace)
    if c == "rainfall-imd":
        y0, _, y1 = args.years.partition("-")
        return cmd_rainfall_imd(db, cfg, directory=args.directory, years=range(int(y0), int(y1 or y0) + 1), source_id=args.source_id)
    if c == "grid-rainfall":
        return cmd_grid_rainfall(db, cfg, min_years=args.min_years, source_id=args.source_id)
    if c == "wells":
        return cmd_wells(db, cfg, stations=args.stations, readings=args.readings, source_id=args.source_id, agency=args.agency)
    if c == "borewells":
        return cmd_borewells(db, cfg, path=args.file, source_id=args.source_id, record_origin=args.record_origin,
                             yield_thresholds=args.yield_thresholds)
    if c == "ves":
        return cmd_ves(db, cfg, path=args.file, source_id=args.source_id, agency=args.agency)
    if c == "coverage":
        return cmd_coverage(db, cfg, status=args.status)
    raise SystemExit(f"unknown command {c}")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not args.database_url:
        print("DATABASE_URL (or --database-url) is required", file=sys.stderr)
        return 2
    cfg = load_state_config(args.state)
    db = Db(args.database_url)
    try:
        rep = run(args, db, cfg)
    except (ValueError, OSError) as e:
        db.rollback()
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0 if _finish(db, rep, dry_run=args.dry_run, skip_invalid=args.skip_invalid, what=args.cmd) else 1


if __name__ == "__main__":
    raise SystemExit(main())
