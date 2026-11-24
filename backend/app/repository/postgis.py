"""PostgreSQL / PostGIS repository (psycopg 3, plain SQL).

Every query filters on `is_demo = %(demo)s`, so a database that contains both synthetic demo rows
and real rows can never mix them: the API reads exactly one of the two sets.
All SQL is kept in the module-level dict `Q` so it can be reviewed (and replayed in tests) in one place.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import date, timedelta
from typing import Any, Iterable, Optional

from ..engine.config import StateConfig
from ..engine.geo import bbox_around
from ..engine.types import (BorewellRecord, ClassifiedUnit, FeatureCell, ObservationWell, PointContext, Radii,
                            Reading, RegionInfo, SourceRef, VesSurvey)
from .base import empty_fc

PT = "ST_SetSRID(ST_MakePoint(%(lon)s,%(lat)s),4326)"
REGION_MAX_KM = 40.0

Q: dict[str, str] = {
    "ping": "SELECT 1 AS ok",
    "state": """SELECT s.state_code, s.name_en, s.name_te, s.coverage_status,
                       ST_XMin(s.coverage_geom) AS x0, ST_YMin(s.coverage_geom) AS y0,
                       ST_XMax(s.coverage_geom) AS x1, ST_YMax(s.coverage_geom) AS y1
                FROM states s WHERE s.state_code = %(state)s""",
    "in_coverage": f"""SELECT ST_Intersects(s.coverage_geom, {PT}) AS ok
                       FROM states s WHERE s.state_code = %(state)s""",
    "in_coverage_many": """SELECT ST_Intersects(s.coverage_geom, ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326)) AS ok
                           FROM states s,
                                unnest(%(lons)s::float8[], %(lats)s::float8[]) WITH ORDINALITY AS t(lon, lat, n)
                           WHERE s.state_code = %(state)s ORDER BY t.n""",
    "locate_polygon": f"""SELECT a.area_id, a.level, a.name_en, a.name_te, a.gw_category, a.gw_category_year, a.source_id
                          FROM admin_areas a
                          WHERE a.state_code = %(state)s AND a.is_demo = %(demo)s AND a.geom IS NOT NULL
                            AND ST_Intersects(a.geom, {PT})""",
    "locate_nearest": f"""SELECT a.area_id, a.level, a.name_en, a.name_te, a.parent_id,
                                 ST_Distance(a.centroid::geography, ({PT})::geography) / 1000.0 AS dist_km
                          FROM admin_areas a
                          WHERE a.state_code = %(state)s AND a.is_demo = %(demo)s AND a.level IN ('mandal','village')
                          ORDER BY a.centroid <-> {PT} LIMIT 1""",
    "chain": """WITH RECURSIVE chain AS (
                    SELECT area_id, parent_id, level, name_en, name_te, gw_category, gw_category_year, source_id
                    FROM admin_areas WHERE area_id = %(id)s
                  UNION ALL
                    SELECT p.area_id, p.parent_id, p.level, p.name_en, p.name_te, p.gw_category, p.gw_category_year, p.source_id
                    FROM admin_areas p JOIN chain c ON p.area_id = c.parent_id)
                SELECT level, name_en, name_te, gw_category, gw_category_year, source_id FROM chain""",
    "cell": f"""SELECT g.cell_id, g.elevation_m, g.slope_deg, g.tpi_m, g.drainage_density, g.lineament_density,
                       g.rainfall_normal_mm, g.rainfall_cv, g.source_ids
                FROM feature_grid g
                WHERE g.state_code = %(state)s AND g.is_demo = %(demo)s AND ST_Intersects(g.geom, {PT}) LIMIT 1""",
    "geology": f"""SELECT u.lithology_class AS class_key, u.formation_name AS name, u.source_id
                   FROM geology_units u
                   WHERE u.state_code = %(state)s AND u.is_demo = %(demo)s AND ST_Intersects(u.geom, {PT}) LIMIT 1""",
    "aquifer": f"""SELECT u.aquifer_class AS class_key, u.aquifer_name AS name, u.source_id
                   FROM aquifer_units u
                   WHERE u.state_code = %(state)s AND u.is_demo = %(demo)s AND ST_Intersects(u.geom, {PT}) LIMIT 1""",
    "soil": f"""SELECT u.soil_class AS class_key, u.soil_name AS name, u.source_id
                FROM soil_units u
                WHERE u.state_code = %(state)s AND u.is_demo = %(demo)s AND ST_Intersects(u.geom, {PT}) LIMIT 1""",
    "wells_near": f"""SELECT w.well_id, w.station_code, w.name, w.agency, w.source_id, ST_Y(w.geom) AS lat, ST_X(w.geom) AS lon
                      FROM observation_wells w
                      WHERE w.state_code = %(state)s AND w.is_demo = %(demo)s
                        AND w.geom && ST_Expand({PT}, %(deg)s)
                        AND ST_DWithin(w.geom::geography, ({PT})::geography, %(meters)s)""",
    "wells_all": """SELECT w.well_id, w.station_code, w.name, w.agency, w.source_id, ST_Y(w.geom) AS lat, ST_X(w.geom) AS lon
                    FROM observation_wells w WHERE w.state_code = %(state)s AND w.is_demo = %(demo)s""",
    "readings": """SELECT r.well_id, r.measured_on, r.season, r.depth_to_water_m
                   FROM water_level_readings r
                   WHERE r.well_id = ANY(%(ids)s) AND r.is_demo = %(demo)s AND r.measured_on >= %(since)s
                   ORDER BY r.well_id, r.measured_on""",
    "borewells_near": f"""SELECT b.borewell_id, ST_Y(b.geom) AS lat, ST_X(b.geom) AS lon, b.depth_ft, b.outcome, b.yield_lpm,
                                 b.drilled_year, b.location_accuracy_m, b.source_id
                          FROM borewell_records b
                          WHERE b.state_code = %(state)s AND b.is_demo = %(demo)s
                            AND b.geom && ST_Expand({PT}, %(deg)s)
                            AND ST_DWithin(b.geom::geography, ({PT})::geography, %(meters)s)""",
    "ves_near": f"""SELECT v.survey_id, ST_Y(v.geom) AS lat, ST_X(v.geom) AS lon, v.method, v.survey_year,
                           v.weathered_thickness_m, v.fracture_zone_top_m, v.fracture_zone_bottom_m,
                           v.interpreted_suitability, v.interpretation_note, v.source_id
                    FROM geophysical_surveys v
                    WHERE v.state_code = %(state)s AND v.is_demo = %(demo)s
                      AND v.geom && ST_Expand({PT}, %(deg)s)
                      AND ST_DWithin(v.geom::geography, ({PT})::geography, %(meters)s)""",
    "rain_nearest": f"""SELECT c.cell_key FROM rainfall_cells c WHERE c.is_demo = %(demo)s
                        ORDER BY c.geom <-> {PT} LIMIT 1""",
    "rain_years": """SELECT r.year, r.annual_mm, r.source_id FROM rainfall_annual r
                     WHERE r.cell_key = %(key)s AND r.is_demo = %(demo)s ORDER BY r.year DESC LIMIT %(n)s""",
    "sources": """SELECT source_id, name_en, name_te, publisher, layer_kind, url, license, retrieved_on,
                         data_last_updated, is_demo, notes
                  FROM data_sources WHERE is_demo = %(demo)s ORDER BY layer_kind, source_id""",
    "search_admin": """SELECT a.area_id, a.level, a.name_en, a.name_te, ST_Y(a.centroid) AS lat, ST_X(a.centroid) AS lon,
                              CASE WHEN a.name_en ILIKE %(prefix)s OR a.name_te ILIKE %(prefix)s THEN 0 ELSE 1 END AS rank,
                              p1.name_en AS p1_en, p1.name_te AS p1_te, p2.name_en AS p2_en, p2.name_te AS p2_te
                       FROM admin_areas a
                       LEFT JOIN admin_areas p1 ON p1.area_id = a.parent_id
                       LEFT JOIN admin_areas p2 ON p2.area_id = p1.parent_id
                       WHERE a.state_code = %(state)s AND a.is_demo = %(demo)s
                         AND (a.name_en ILIKE %(contains)s OR a.name_te ILIKE %(contains)s)
                       ORDER BY rank, CASE a.level WHEN 'district' THEN 0 WHEN 'mandal' THEN 1 ELSE 2 END, a.name_en
                       LIMIT %(limit)s""",
    "search_pin": """SELECT p.pincode, p.office_name, ST_Y(p.centroid) AS lat, ST_X(p.centroid) AS lon,
                            d.name_en AS d_en, d.name_te AS d_te
                     FROM pincodes p LEFT JOIN admin_areas d ON d.area_id = p.district_area_id
                     WHERE p.state_code = %(state)s AND p.is_demo = %(demo)s AND p.pincode LIKE %(prefix)s
                     ORDER BY p.pincode, p.office_name LIMIT %(limit)s""",
    "regions": """SELECT a.area_id, a.name_en, a.name_te, ST_Y(a.centroid) AS lat, ST_X(a.centroid) AS lon
                  FROM admin_areas a
                  WHERE a.state_code = %(state)s AND a.is_demo = %(demo)s AND a.level = %(level)s
                    AND (%(parent)s::bigint IS NULL OR a.parent_id = %(parent)s)
                  ORDER BY a.name_en""",
    "potential_geojson": """SELECT g.cell_id, p.regional_class AS klass, p.regional_score AS score, p.coverage,
                                   ST_AsGeoJSON(g.geom, 5) AS geom
                            FROM potential_cells p JOIN feature_grid g ON g.cell_id = p.cell_id
                            WHERE p.is_demo = %(demo)s AND g.state_code = %(state)s
                              AND g.geom && ST_MakeEnvelope(%(x0)s, %(y0)s, %(x1)s, %(y1)s, 4326)
                            LIMIT %(limit)s""",
    "wells_geojson": """SELECT w.station_code, w.agency, ST_AsGeoJSON(w.geom, 5) AS geom,
                               (SELECT count(*) FROM water_level_readings r WHERE r.well_id = w.well_id) AS n_readings
                        FROM observation_wells w
                        WHERE w.state_code = %(state)s AND w.is_demo = %(demo)s
                          AND w.geom && ST_MakeEnvelope(%(x0)s, %(y0)s, %(x1)s, %(y1)s, 4326) LIMIT %(limit)s""",
    "borewells_geojson": """SELECT b.outcome, b.depth_ft, b.drilled_year, ST_AsGeoJSON(b.geom, 5) AS geom
                           FROM borewell_records b
                           WHERE b.state_code = %(state)s AND b.is_demo = %(demo)s
                             AND b.geom && ST_MakeEnvelope(%(x0)s, %(y0)s, %(x1)s, %(y1)s, 4326) LIMIT %(limit)s""",
    "coverage_geojson": "SELECT ST_AsGeoJSON(s.coverage_geom, 4) AS geom FROM states s WHERE s.state_code = %(state)s",
    "layer_counts": """SELECT
        (SELECT count(*) FROM admin_areas WHERE is_demo = %(demo)s AND state_code = %(state)s) AS admin,
        (SELECT count(*) FROM pincodes WHERE is_demo = %(demo)s AND state_code = %(state)s) AS pincode,
        (SELECT count(*) FROM geology_units WHERE is_demo = %(demo)s AND state_code = %(state)s) AS geology,
        (SELECT count(*) FROM soil_units WHERE is_demo = %(demo)s AND state_code = %(state)s) AS soil,
        (SELECT count(*) FROM aquifer_units WHERE is_demo = %(demo)s AND state_code = %(state)s) AS aquifer,
        (SELECT count(*) FROM feature_grid WHERE is_demo = %(demo)s AND state_code = %(state)s) AS terrain,
        (SELECT count(*) FROM rainfall_cells WHERE is_demo = %(demo)s) AS rainfall,
        (SELECT count(*) FROM observation_wells WHERE is_demo = %(demo)s AND state_code = %(state)s) AS water_level,
        (SELECT count(*) FROM borewell_records WHERE is_demo = %(demo)s AND state_code = %(state)s) AS borewell,
        (SELECT count(*) FROM geophysical_surveys WHERE is_demo = %(demo)s AND state_code = %(state)s) AS geophysics""",
    "save_contact": """INSERT INTO contact_messages (name, email, phone, message, lang)
                       VALUES (%(name)s, %(email)s, %(phone)s, %(message)s, %(lang)s) RETURNING message_id""",
    "training_points": """SELECT ST_Y(b.geom) AS lat, ST_X(b.geom) AS lon, b.outcome FROM borewell_records b
                          WHERE b.state_code = %(state)s AND b.is_demo = %(demo)s""",
    "cell_centroids": """SELECT g.cell_id, ST_Y(g.centroid) AS lat, ST_X(g.centroid) AS lon FROM feature_grid g
                         WHERE g.state_code = %(state)s AND g.is_demo = %(demo)s ORDER BY g.cell_id""",
    "cell_inputs": """SELECT g.cell_id, ST_Y(g.centroid) AS lat, ST_X(g.centroid) AS lon, g.elevation_m, g.slope_deg, g.tpi_m,
                             g.drainage_density, g.lineament_density, g.rainfall_normal_mm, g.rainfall_cv, g.source_ids,
                             lu.class_key AS lith, lu.name AS lith_name, lu.source_id AS lith_src,
                             au.class_key AS aq, au.name AS aq_name, au.source_id AS aq_src,
                             su.class_key AS soil, su.name AS soil_name, su.source_id AS soil_src
                      FROM feature_grid g
                      LEFT JOIN LATERAL (SELECT u.lithology_class AS class_key, u.formation_name AS name, u.source_id
                                         FROM geology_units u WHERE u.is_demo = %(demo)s AND ST_Intersects(u.geom, g.centroid) LIMIT 1) lu ON true
                      LEFT JOIN LATERAL (SELECT u.aquifer_class AS class_key, u.aquifer_name AS name, u.source_id
                                         FROM aquifer_units u WHERE u.is_demo = %(demo)s AND ST_Intersects(u.geom, g.centroid) LIMIT 1) au ON true
                      LEFT JOIN LATERAL (SELECT u.soil_class AS class_key, u.soil_name AS name, u.source_id
                                         FROM soil_units u WHERE u.is_demo = %(demo)s AND ST_Intersects(u.geom, g.centroid) LIMIT 1) su ON true
                      WHERE g.state_code = %(state)s AND g.is_demo = %(demo)s AND g.cell_id > %(after)s
                      ORDER BY g.cell_id LIMIT %(batch)s""",
    "upsert_potential": """INSERT INTO potential_cells (cell_id, regional_score, regional_class, coverage, factor_scores,
                                                          method_version, computed_at, is_demo)
                           VALUES (%(cell_id)s, %(score)s, %(klass)s, %(coverage)s, %(factors)s::jsonb, %(version)s, now(), %(demo)s)
                           ON CONFLICT (cell_id) DO UPDATE SET regional_score = EXCLUDED.regional_score,
                               regional_class = EXCLUDED.regional_class, coverage = EXCLUDED.coverage,
                               factor_scores = EXCLUDED.factor_scores, method_version = EXCLUDED.method_version,
                               computed_at = now(), is_demo = EXCLUDED.is_demo""",
}


def _f(v) -> Optional[float]:
    return None if v is None else float(v)


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PostgisRepository:
    def __init__(self, database_url: str, cfg: StateConfig, data_mode: str, *, pool_size: int = 10):
        from psycopg.rows import dict_row            # imported lazily: memory mode needs no DB driver
        from psycopg_pool import ConnectionPool
        self.cfg = cfg
        self.data_mode = data_mode
        self.state = cfg.code
        self.demo = data_mode == "demo"
        self.pool = ConnectionPool(database_url, min_size=1, max_size=pool_size, kwargs={"row_factory": dict_row},
                                   open=True, timeout=10)
        self._src_cache: tuple[float, dict[str, SourceRef]] = (0.0, {})
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ plumbing
    def _p(self, **kw) -> dict:
        return {"state": self.state, "demo": self.demo, **kw}

    def _all(self, key: str, **params) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(Q[key], self._p(**params)).fetchall()

    def _one(self, key: str, **params) -> Optional[dict]:
        rows = self._all(key, **params)
        return rows[0] if rows else None

    def close(self) -> None:
        self.pool.close()

    def ping(self) -> bool:
        try:
            return bool(self._one("ping"))
        except Exception:
            return False

    # ------------------------------------------------------------------ sources
    def _sources(self) -> dict[str, SourceRef]:
        with self._lock:
            ts, cached = self._src_cache
            if cached and time.time() - ts < 300:
                return cached
        rows = self._all("sources")
        out = {r["source_id"]: SourceRef(
            source_id=r["source_id"], name_en=r["name_en"], name_te=r["name_te"], publisher=r["publisher"],
            layer_kind=r["layer_kind"], url=r["url"], license=r["license"], retrieved_on=r["retrieved_on"],
            data_last_updated=r["data_last_updated"], is_demo=r["is_demo"], notes=r["notes"]) for r in rows}
        with self._lock:
            self._src_cache = (time.time(), out)
        return out

    # ------------------------------------------------------------------ state / coverage
    def state_info(self) -> dict:
        r = self._one("state")
        if r is None:
            # Fresh production database: nothing loaded yet. Start anyway and say so (every point is then "outside the
            # covered area") instead of failing; `python -m scripts.etl.load state` creates the row.
            return {"code": self.cfg.code, "name": {"en": self.cfg.name["en"], "te": self.cfg.name["te"]},
                    "coverage_status": "planned", "bounds": self.cfg.map_bounds, "coverage_bbox": None}
        bbox = [r["x0"], r["y0"], r["x1"], r["y1"]] if r["x0"] is not None else None
        return {"code": r["state_code"], "name": {"en": r["name_en"], "te": r["name_te"] or r["name_en"]},
                "coverage_status": r["coverage_status"], "bounds": self.cfg.map_bounds, "coverage_bbox": bbox}

    def _in_coverage(self, lat: float, lon: float) -> bool:
        r = self._one("in_coverage", lat=lat, lon=lon)
        return bool(r and r["ok"])

    # ------------------------------------------------------------------ region lookup
    def _locate(self, lat: float, lon: float) -> Optional[RegionInfo]:
        (s_lat0, s_lon0), (s_lat1, s_lon1) = self.cfg.map_bounds
        if not (s_lat0 <= lat <= s_lat1 and s_lon0 <= lon <= s_lon1):
            return None
        st = self._one("state")
        info = RegionInfo(state_code=self.state, state_en=st["name_en"] if st else self.cfg.name["en"],
                          state_te=(st["name_te"] if st else self.cfg.name["te"]), method="polygon")
        rows = self._all("locate_polygon", lat=lat, lon=lon)
        if rows:
            for r in rows:
                self._apply_level(info, r)
            return info
        near = self._one("locate_nearest", lat=lat, lon=lon)
        if near is None or near["dist_km"] is None or float(near["dist_km"]) > REGION_MAX_KM:
            info.method = "nearest_place"
            return info
        info.method = "nearest_place"
        info.nearest_place_km = float(near["dist_km"])
        for r in self._all("chain", id=near["area_id"]):
            self._apply_level(info, r)
        return info

    @staticmethod
    def _apply_level(info: RegionInfo, r: dict) -> None:
        if r["level"] == "village":
            info.village_en, info.village_te = r["name_en"], r["name_te"]
        elif r["level"] == "mandal":
            info.mandal_en, info.mandal_te = r["name_en"], r["name_te"]
        elif r["level"] == "district":
            info.district_en, info.district_te = r["name_en"], r["name_te"]
            info.gw_category, info.gw_category_year = r["gw_category"], r["gw_category_year"]
            info.gw_category_source_id = r["source_id"] if r["gw_category"] else None

    # ------------------------------------------------------------------ analysis context
    @staticmethod
    def _unit(row) -> Optional[ClassifiedUnit]:
        return ClassifiedUnit(row["class_key"], row["name"], row["source_id"]) if row else None

    def point_context(self, lat: float, lon: float, radii: Radii) -> PointContext:
        ctx = PointContext(lat=lat, lon=lon, in_coverage=self._in_coverage(lat, lon), data_mode=self.data_mode,
                           sources=self._sources())
        ctx.region = self._locate(lat, lon)
        if not ctx.in_coverage:
            return ctx
        c = self._one("cell", lat=lat, lon=lon)
        if c:
            sid = c["source_ids"] if isinstance(c["source_ids"], dict) else json.loads(c["source_ids"] or "{}")
            ctx.cell = FeatureCell(c["cell_id"], _f(c["elevation_m"]), _f(c["slope_deg"]), _f(c["tpi_m"]),
                                   _f(c["drainage_density"]), _f(c["lineament_density"]),
                                   _f(c["rainfall_normal_mm"]), _f(c["rainfall_cv"]), sid)
        ctx.lithology = self._unit(self._one("geology", lat=lat, lon=lon))
        ctx.aquifer = self._unit(self._one("aquifer", lat=lat, lon=lon))
        ctx.soil = self._unit(self._one("soil", lat=lat, lon=lon))

        def near(key: str, km: float) -> list[dict]:
            x0, y0, x1, y1 = bbox_around(lat, lon, km)
            deg = max(x1 - x0, y1 - y0) / 2.0
            return self._all(key, lat=lat, lon=lon, deg=deg, meters=km * 1000.0)

        wells = near("wells_near", radii.wells_km)
        if wells:
            since = date.today() - timedelta(days=int(365.25 * 12))
            by_id: dict[int, ObservationWell] = {}
            for w in wells:
                by_id[w["well_id"]] = ObservationWell(w["well_id"], w["station_code"], float(w["lat"]), float(w["lon"]),
                                                      [], w["name"], w["agency"], w["source_id"])
            for r in self._all("readings", ids=list(by_id), since=since):
                by_id[r["well_id"]].readings.append(Reading(r["measured_on"], r["season"], float(r["depth_to_water_m"])))
            ctx.wells = list(by_id.values())
        ctx.borewells = [BorewellRecord(b["borewell_id"], float(b["lat"]), float(b["lon"]), float(b["depth_ft"]),
                                        b["outcome"], _f(b["yield_lpm"]), b["drilled_year"], b["location_accuracy_m"],
                                        b["source_id"]) for b in near("borewells_near", radii.borewells_km)]
        ctx.ves = [VesSurvey(v["survey_id"], float(v["lat"]), float(v["lon"]), v["method"], v["interpreted_suitability"],
                             v["survey_year"], _f(v["weathered_thickness_m"]), _f(v["fracture_zone_top_m"]),
                             _f(v["fracture_zone_bottom_m"]), v["interpretation_note"], v["source_id"])
                   for v in near("ves_near", radii.ves_km)]
        rc = self._one("rain_nearest", lat=lat, lon=lon)
        if rc:
            yrs = self._all("rain_years", key=rc["cell_key"], n=radii.rainfall_years)
            ctx.rainfall_years = sorted((int(r["year"]), float(r["annual_mm"])) for r in yrs)
            ctx.rainfall_source_id = yrs[0]["source_id"] if yrs else None
        return ctx

    # ------------------------------------------------------------------ search
    def search(self, q: str, limit: int = 10) -> list[dict]:
        q = (q or "").strip()
        if len(q) < 2:
            return []
        st = self.state_info()
        out: list[dict] = []
        if q.isdigit():
            for r in self._all("search_pin", prefix=_like_escape(q) + "%", limit=limit):
                d_en, d_te = r["d_en"], r["d_te"]
                out.append({"type": "pincode", "id": r["pincode"], "pincode": r["pincode"],
                            "name": {"en": f"{r['pincode']} - {r['office_name']}", "te": f"{r['pincode']} - {r['office_name']}"},
                            "context": {"en": ", ".join(x for x in (d_en, st["name"]["en"]) if x),
                                        "te": ", ".join(x for x in (d_te or d_en, st["name"]["te"]) if x)},
                            "lat": float(r["lat"]), "lon": float(r["lon"])})
        rows = self._all("search_admin", prefix=_like_escape(q) + "%", contains="%" + _like_escape(q) + "%", limit=limit)
        for r in rows:
            parts_en = [x for x in (r["p1_en"], r["p2_en"], st["name"]["en"]) if x]
            parts_te = [(te or en) for en, te in ((r["p1_en"], r["p1_te"]), (r["p2_en"], r["p2_te"]))
                        if en] + [st["name"]["te"]]
            out.append({"type": r["level"], "id": r["area_id"], "pincode": None,
                        "name": {"en": r["name_en"], "te": r["name_te"] or r["name_en"]},
                        "context": {"en": ", ".join(parts_en), "te": ", ".join(parts_te)},
                        "lat": float(r["lat"]), "lon": float(r["lon"])})
        out = out[:limit]
        if out:
            flags = self._all("in_coverage_many", lons=[o["lon"] for o in out], lats=[o["lat"] for o in out])
            for o, f in zip(out, flags):
                o["in_coverage"] = bool(f["ok"])
        return out

    def regions(self, level: str, parent_id: Optional[int]) -> list[dict]:
        if level == "state":
            st = self.state_info()
            (a, b), (c, d) = self.cfg.map_bounds
            return [{"id": st["code"], "name": st["name"], "lat": (a + c) / 2, "lon": (b + d) / 2}]
        if level != "district" and parent_id is None:
            return []                                    # never list every mandal/village of a state
        return [{"id": r["area_id"], "name": {"en": r["name_en"], "te": r["name_te"] or r["name_en"]},
                 "lat": float(r["lat"]), "lon": float(r["lon"])}
                for r in self._all("regions", level=level, parent=parent_id)]

    # ------------------------------------------------------------------ GeoJSON layers
    def potential_geojson(self, bbox, limit: int) -> dict:
        x0, y0, x1, y1 = bbox
        rows = self._all("potential_geojson", x0=x0, y0=y0, x1=x1, y1=y1, limit=limit)
        feats = [{"type": "Feature", "id": r["cell_id"],
                  "properties": {"id": r["cell_id"], "class": r["klass"], "score": _f(r["score"]),
                                 "coverage": _f(r["coverage"])},
                  "geometry": json.loads(r["geom"])} for r in rows]
        return {"type": "FeatureCollection", "features": feats, "truncated": len(feats) >= limit}

    def wells_geojson(self, bbox, limit: int) -> dict:
        x0, y0, x1, y1 = bbox
        rows = self._all("wells_geojson", x0=x0, y0=y0, x1=x1, y1=y1, limit=limit)
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"code": r["station_code"], "agency": r["agency"], "n_readings": r["n_readings"]},
             "geometry": json.loads(r["geom"])} for r in rows]}

    def borewells_geojson(self, bbox, limit: int) -> dict:
        x0, y0, x1, y1 = bbox
        rows = self._all("borewells_geojson", x0=x0, y0=y0, x1=x1, y1=y1, limit=limit)
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"outcome": r["outcome"], "depth_ft": _f(r["depth_ft"]), "year": r["drilled_year"]},
             "geometry": json.loads(r["geom"])} for r in rows]}

    def coverage_geojson(self) -> dict:
        r = self._one("coverage_geojson")
        if not r or not r["geom"]:
            return empty_fc()
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"state": self.state, "demo": self.demo}, "geometry": json.loads(r["geom"])}]}

    # ------------------------------------------------------------------ meta
    def datasets(self) -> list[dict]:
        from ..present import source_to_dict
        return [source_to_dict(s) for s in self._sources().values()]

    def layer_counts(self) -> dict[str, int]:
        r = self._one("layer_counts") or {}
        return {k: int(v) for k, v in r.items()}

    def save_contact(self, name, email, phone, message, lang) -> int:
        with self.pool.connection() as conn:
            row = conn.execute(Q["save_contact"], {"name": name, "email": email, "phone": phone,
                                                    "message": message, "lang": lang}).fetchone()
            return int(row["message_id"])

    # ------------------------------------------------------------------ batch helpers
    def training_points(self) -> Iterable[tuple[float, float, str]]:
        for r in self._all("training_points"):
            yield float(r["lat"]), float(r["lon"]), r["outcome"]

    def cell_centroids(self) -> Iterable[tuple[int, float, float]]:
        for r in self._all("cell_centroids"):
            yield r["cell_id"], float(r["lat"]), float(r["lon"])

    def iter_cell_inputs(self, batch: int = 2000) -> Iterable[list[dict]]:
        after = 0
        while True:
            rows = self._all("cell_inputs", after=after, batch=batch)
            if not rows:
                return
            yield rows
            after = rows[-1]["cell_id"]

    def iter_regional_inputs(self, batch: int = 2000):
        """Yield lists of (lat, lon, FeatureCell, lithology, aquifer, soil) for every grid cell (batch pre-computation)."""
        for rows in self.iter_cell_inputs(batch):
            out = []
            for r in rows:
                sid = r["source_ids"] if isinstance(r["source_ids"], dict) else json.loads(r["source_ids"] or "{}")
                cell = FeatureCell(r["cell_id"], _f(r["elevation_m"]), _f(r["slope_deg"]), _f(r["tpi_m"]),
                                   _f(r["drainage_density"]), _f(r["lineament_density"]),
                                   _f(r["rainfall_normal_mm"]), _f(r["rainfall_cv"]), sid)

                def unit(k: str) -> Optional[ClassifiedUnit]:
                    return ClassifiedUnit(r[k], r[k + "_name"], r[k + "_src"]) if r[k] else None

                out.append((float(r["lat"]), float(r["lon"]), cell, unit("lith"), unit("aq"), unit("soil")))
            yield out

    def load_all_wells(self, today: date) -> list[ObservationWell]:
        wells = {w["well_id"]: ObservationWell(w["well_id"], w["station_code"], float(w["lat"]), float(w["lon"]), [],
                                               w["name"], w["agency"], w["source_id"]) for w in self._all("wells_all")}
        since = today - timedelta(days=int(365.25 * 12))
        for r in self._all("readings", ids=list(wells), since=since):
            wells[r["well_id"]].readings.append(Reading(r["measured_on"], r["season"], float(r["depth_to_water_m"])))
        return list(wells.values())

    def write_potential(self, rows: list[dict]) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(Q["upsert_potential"], [{**r, "demo": self.demo} for r in rows])
