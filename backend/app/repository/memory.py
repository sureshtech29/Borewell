"""MemoryRepository: serves a `Dataset` from RAM. Used for tests and for a database-free
local demo (APP_DATA_BACKEND=memory). It implements exactly the same behaviour as the
PostGIS repository, only with numpy instead of SQL."""
from __future__ import annotations

import threading
from datetime import date
from typing import Iterable, Optional

import numpy as np

from ..engine.config import StateConfig
from ..engine.geo import haversine_km
from ..engine.scoring import RegionalResult, regional_for_point
from ..engine.types import (ClassifiedUnit, PointContext, Radii, RegionInfo, SourceRef)
from ..engine.wells import PreparedWells, prepare_wells
from ..present import source_to_dict
from .base import empty_fc
from .dataset import Dataset, GridCell, PolyUnit

REGION_MAX_KM = 40.0


def _in_ring(lon: float, lat: float, ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class _UnitIndex:
    def __init__(self, units: list[PolyUnit]):
        self.units = units
        b = np.array([u.bbox for u in units], dtype=float) if units else np.zeros((0, 4))
        self.minx, self.miny, self.maxx, self.maxy = b[:, 0], b[:, 1], b[:, 2], b[:, 3]

    def lookup(self, lat: float, lon: float) -> Optional[ClassifiedUnit]:
        if not self.units:
            return None
        mask = (self.minx <= lon) & (lon <= self.maxx) & (self.miny <= lat) & (lat <= self.maxy)
        for i in np.where(mask)[0]:
            u = self.units[i]
            if _in_ring(lon, lat, u.ring):
                return ClassifiedUnit(u.class_key, u.name, u.source_id)
        return None


class MemoryRepository:
    def __init__(self, ds: Dataset, cfg: StateConfig):
        self.ds = ds
        self.cfg = cfg
        self.data_mode = "demo" if ds.is_demo else "production"
        self._geo = _UnitIndex(ds.geology)
        self._soil = _UnitIndex(ds.soil)
        self._aq = _UnitIndex(ds.aquifer)
        self._contacts: list[dict] = []
        self._potential: Optional[list[tuple[GridCell, RegionalResult]]] = None
        self._lock = threading.Lock()
        self._places = {p.place_id: p for p in ds.places}
        self._place_lat = np.array([p.lat for p in ds.places], dtype=float)
        self._place_lon = np.array([p.lon for p in ds.places], dtype=float)
        self._well_lat = np.array([w.lat for w in ds.wells], dtype=float)
        self._well_lon = np.array([w.lon for w in ds.wells], dtype=float)
        self._bw_lat = np.array([b.lat for b in ds.borewells], dtype=float)
        self._bw_lon = np.array([b.lon for b in ds.borewells], dtype=float)
        self._ves_lat = np.array([v.lat for v in ds.ves], dtype=float)
        self._ves_lon = np.array([v.lon for v in ds.ves], dtype=float)
        self._rain_lat = np.array([r.lat for r in ds.rain_cells], dtype=float)
        self._rain_lon = np.array([r.lon for r in ds.rain_cells], dtype=float)
        self._prepared: Optional[PreparedWells] = None
        self._prepared_for: Optional[date] = None

    # ------------------------------------------------------------------ basics
    def ping(self) -> bool:
        return True

    def state_info(self) -> dict:
        ds = self.ds
        return {
            "code": ds.state_code,
            "name": {"en": ds.state_en, "te": ds.state_te},
            "coverage_status": "demo" if ds.is_demo else "active",
            "bounds": self.cfg.map_bounds,
            "coverage_bbox": list(ds.coverage_bbox),
        }

    def _in_coverage(self, lat: float, lon: float) -> bool:
        x0, y0, x1, y1 = self.ds.coverage_bbox
        return x0 <= lon <= x1 and y0 <= lat <= y1

    def _cell_at(self, lat: float, lon: float) -> Optional[GridCell]:
        ds = self.ds
        nrows, ncols = ds.grid_shape
        ix = int((lon - ds.grid_origin[0]) // ds.grid_step)
        iy = int((lat - ds.grid_origin[1]) // ds.grid_step)
        if 0 <= ix < ncols and 0 <= iy < nrows:
            return ds.cells[iy * ncols + ix]
        return None

    # ------------------------------------------------------------------ region
    def _locate(self, lat: float, lon: float) -> Optional[RegionInfo]:
        ds = self.ds
        s_lat0, s_lon0 = self.cfg.map_bounds[0]
        s_lat1, s_lon1 = self.cfg.map_bounds[1]
        if not (s_lat0 <= lat <= s_lat1 and s_lon0 <= lon <= s_lon1):
            return None
        info = RegionInfo(state_code=ds.state_code, state_en=ds.state_en, state_te=ds.state_te,
                          method="nearest_place")
        if not ds.places:
            return info
        d = haversine_km(lat, lon, self._place_lat, self._place_lon)
        fine = [i for i, p in enumerate(ds.places) if p.level in ("mandal", "village")]
        pick = None
        if fine:
            j = min(fine, key=lambda i: d[i])
            if d[j] <= REGION_MAX_KM:
                pick = j
        if pick is None:
            j = int(np.argmin(d))
            if d[j] <= REGION_MAX_KM * 1.5:
                pick = j
        if pick is None:
            return info
        p = ds.places[pick]
        info.nearest_place_km = float(d[pick])
        chain = []
        cur = p
        while cur is not None:
            chain.append(cur)
            cur = self._places.get(cur.parent_id) if cur.parent_id else None
        for c in chain:
            if c.level == "village":
                info.village_en, info.village_te = c.name_en, c.name_te
            elif c.level == "mandal":
                info.mandal_en, info.mandal_te = c.name_en, c.name_te
            elif c.level == "district":
                info.district_en, info.district_te = c.name_en, c.name_te
                info.gw_category, info.gw_category_year = c.gw_category, c.gw_category_year
                info.gw_category_source_id = c.gw_category_source_id
        return info

    # ------------------------------------------------------------------ analysis context
    def point_context(self, lat: float, lon: float, radii: Radii) -> PointContext:
        ds = self.ds
        ctx = PointContext(lat=lat, lon=lon, in_coverage=self._in_coverage(lat, lon),
                           data_mode=self.data_mode, sources=dict(ds.sources))
        ctx.region = self._locate(lat, lon)
        if not ctx.in_coverage:
            return ctx
        gc = self._cell_at(lat, lon)
        ctx.cell = gc.cell if gc else None
        ctx.lithology = self._geo.lookup(lat, lon)
        ctx.aquifer = self._aq.lookup(lat, lon)
        ctx.soil = self._soil.lookup(lat, lon)

        if len(self._well_lat):
            d = haversine_km(lat, lon, self._well_lat, self._well_lon)
            ctx.wells = [ds.wells[i] for i in np.where(d <= radii.wells_km)[0]]
        if len(self._bw_lat):
            d = haversine_km(lat, lon, self._bw_lat, self._bw_lon)
            ctx.borewells = [ds.borewells[i] for i in np.where(d <= radii.borewells_km)[0]]
        if len(self._ves_lat):
            d = haversine_km(lat, lon, self._ves_lat, self._ves_lon)
            ctx.ves = [ds.ves[i] for i in np.where(d <= radii.ves_km)[0]]
        if len(self._rain_lat):
            d = haversine_km(lat, lon, self._rain_lat, self._rain_lon)
            rc = ds.rain_cells[int(np.argmin(d))]
            years = sorted(rc.annual)[-radii.rainfall_years:]
            ctx.rainfall_years = [(y, rc.annual[y][0]) for y in years]
            ctx.rainfall_source_id = "demo_rainfall" if ds.is_demo else None
        return ctx

    # ------------------------------------------------------------------ batch map stage
    def _prepared_wells(self, today: date) -> PreparedWells:
        if self._prepared is None or self._prepared_for != today:
            self._prepared = prepare_wells(self.ds.wells, self.cfg, today)
            self._prepared_for = today
        return self._prepared

    def potential_cells(self, today: Optional[date] = None) -> list[tuple[GridCell, RegionalResult]]:
        today = today or date.today()
        with self._lock:
            if self._potential is not None and self._prepared_for == today:
                return self._potential
            pw = self._prepared_wells(today)
            out = []
            for gc in self.ds.cells:
                lat, lon = gc.centroid
                r = regional_for_point(lat=lat, lon=lon, cell=gc.cell,
                                       lithology=self._geo.lookup(lat, lon),
                                       aquifer=self._aq.lookup(lat, lon),
                                       soil=self._soil.lookup(lat, lon),
                                       prepared_wells=pw, cfg=self.cfg)
                out.append((gc, r))
            self._potential = out
            return out

    # ------------------------------------------------------------------ search & regions
    def _ctx_labels(self, p) -> dict:
        names_en, names_te = [], []
        cur = self._places.get(p.parent_id) if p.parent_id else None
        while cur is not None:
            names_en.append(cur.name_en)
            names_te.append(cur.name_te)
            cur = self._places.get(cur.parent_id) if cur.parent_id else None
        names_en.append(self.ds.state_en)
        names_te.append(self.ds.state_te)
        return {"en": ", ".join(names_en), "te": ", ".join(names_te)}

    def search(self, q: str, limit: int = 10) -> list[dict]:
        q = (q or "").strip()
        if len(q) < 2:
            return []
        ql = q.casefold()
        ds = self.ds
        res: list[tuple[int, dict]] = []

        if q.isdigit():
            for pin in ds.pins:
                if pin.pincode.startswith(q):
                    dist = self._places.get(pin.district_place_id)
                    res.append((0 if pin.pincode == q else 1, {
                        "type": "pincode", "id": pin.pincode,
                        "name": {"en": f"{pin.pincode} - {pin.office_name}", "te": f"{pin.pincode} - {pin.office_name}"},
                        "context": {"en": (dist.name_en + ", " if dist else "") + ds.state_en,
                                    "te": (dist.name_te + ", " if dist else "") + ds.state_te},
                        "lat": pin.lat, "lon": pin.lon, "in_coverage": self._in_coverage(pin.lat, pin.lon),
                        "pincode": pin.pincode}))
        if ds.state_en.casefold().startswith(ql) or ds.state_te.startswith(q):
            res.append((0, {"type": "state", "id": ds.state_code, "name": {"en": ds.state_en, "te": ds.state_te},
                            "context": {"en": "India", "te": "భారతదేశం"},
                            "lat": (self.cfg.map_bounds[0][0] + self.cfg.map_bounds[1][0]) / 2,
                            "lon": (self.cfg.map_bounds[0][1] + self.cfg.map_bounds[1][1]) / 2,
                            "in_coverage": True, "pincode": None}))
        rank_level = {"district": 0, "mandal": 1, "village": 2}
        for p in ds.places:
            en, te = p.name_en.casefold(), p.name_te
            if en.startswith(ql) or te.startswith(q):
                score = 0
            elif ql in en or q in te:
                score = 1
            else:
                continue
            res.append((score * 10 + rank_level[p.level], {
                "type": p.level, "id": p.place_id, "name": {"en": p.name_en, "te": p.name_te},
                "context": self._ctx_labels(p), "lat": p.lat, "lon": p.lon,
                "in_coverage": self._in_coverage(p.lat, p.lon), "pincode": None}))
        res.sort(key=lambda t: (t[0], t[1]["name"]["en"]))
        return [r for _, r in res[:limit]]

    def regions(self, level: str, parent_id: Optional[int]) -> list[dict]:
        ds = self.ds
        if level == "state":
            return [{"id": ds.state_code, "name": {"en": ds.state_en, "te": ds.state_te},
                     "lat": (self.cfg.map_bounds[0][0] + self.cfg.map_bounds[1][0]) / 2,
                     "lon": (self.cfg.map_bounds[0][1] + self.cfg.map_bounds[1][1]) / 2}]
        out = []
        for p in ds.places:
            if p.level != level:
                continue
            if level != "district" and p.parent_id != parent_id:
                continue
            out.append({"id": p.place_id, "name": {"en": p.name_en, "te": p.name_te}, "lat": p.lat, "lon": p.lon,
                        "in_coverage": self._in_coverage(p.lat, p.lon)})
        out.sort(key=lambda r: r["name"]["en"])
        return out

    # ------------------------------------------------------------------ GeoJSON layers
    def potential_geojson(self, bbox, limit: int) -> dict:
        x0, y0, x1, y1 = bbox
        feats = []
        for gc, r in self.potential_cells():
            if gc.lon1 < x0 or gc.lon0 > x1 or gc.lat1 < y0 or gc.lat0 > y1:
                continue
            feats.append({"type": "Feature", "id": gc.cell.cell_id,
                          "properties": {"id": gc.cell.cell_id, "class": r.klass,
                                         "score": r.score, "coverage": round(r.coverage, 2)},
                          "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in gc.ring]]}})
            if len(feats) >= limit:
                break
        return {"type": "FeatureCollection", "features": feats, "truncated": len(feats) >= limit}

    def wells_geojson(self, bbox, limit: int) -> dict:
        x0, y0, x1, y1 = bbox
        feats = []
        for w in self.ds.wells:
            if x0 <= w.lon <= x1 and y0 <= w.lat <= y1:
                feats.append({"type": "Feature", "properties": {"code": w.station_code, "agency": w.agency,
                                                                "n_readings": len(w.readings)},
                              "geometry": {"type": "Point", "coordinates": [w.lon, w.lat]}})
            if len(feats) >= limit:
                break
        return {"type": "FeatureCollection", "features": feats}

    def borewells_geojson(self, bbox, limit: int) -> dict:
        x0, y0, x1, y1 = bbox
        feats = []
        for b in self.ds.borewells:
            if x0 <= b.lon <= x1 and y0 <= b.lat <= y1:
                feats.append({"type": "Feature",
                              "properties": {"outcome": b.outcome, "depth_ft": b.depth_ft, "year": b.drilled_year},
                              "geometry": {"type": "Point", "coordinates": [b.lon, b.lat]}})
            if len(feats) >= limit:
                break
        return {"type": "FeatureCollection", "features": feats}

    def coverage_geojson(self) -> dict:
        x0, y0, x1, y1 = self.ds.coverage_bbox
        ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
        return {"type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"state": self.ds.state_code, "demo": self.ds.is_demo},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}]}

    # ------------------------------------------------------------------ meta
    def datasets(self) -> list[dict]:
        out = []
        for s in self.ds.sources.values():
            out.append(source_to_dict(s))
        return out

    def layer_counts(self) -> dict[str, int]:
        ds = self.ds
        return {"admin": len(ds.places), "pincode": len(ds.pins), "geology": len(ds.geology),
                "soil": len(ds.soil), "aquifer": len(ds.aquifer), "terrain": len(ds.cells),
                "rainfall": len(ds.rain_cells), "water_level": len(ds.wells),
                "borewell": len(ds.borewells), "geophysics": len(ds.ves)}

    def save_contact(self, name, email, phone, message, lang) -> int:
        self._contacts.append({"name": name, "email": email, "phone": phone, "message": message, "lang": lang})
        return len(self._contacts)

    def training_points(self) -> Iterable[tuple[float, float, str]]:
        for b in self.ds.borewells:
            yield b.lat, b.lon, b.outcome

    def cell_centroids(self) -> Iterable[tuple[int, float, float]]:
        for gc in self.ds.cells:
            lat, lon = gc.centroid
            yield gc.cell.cell_id, lat, lon

