"""Water-table summary from CGWB / State Ground Water Department observation wells.

`depth to water` is the depth of the water table below ground level (m bgl). It is
NOT the depth to which a borewell must be drilled - see engine/depth.py for that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

from .config import StateConfig
from .geo import haversine_km
from .types import ObservationWell


@dataclass
class WellUsed:
    station_code: str
    distance_km: float
    pre_monsoon_m: Optional[float]
    post_monsoon_m: Optional[float]
    latest_on: Optional[date]


@dataclass
class WaterTable:
    available: bool
    reason: Optional[str]                      # why not available
    radius_km: float
    n_wells: int = 0                           # wells in radius with a reading in the window
    n_pre: int = 0                             # ... with a pre-monsoon value
    nearest_km: Optional[float] = None
    pre_idw_m: Optional[float] = None          # used by the scoring model
    pre_range_m: Optional[tuple[float, float]] = None   # min..max over contributing wells
    post_idw_m: Optional[float] = None
    post_range_m: Optional[tuple[float, float]] = None
    latest_reading_on: Optional[date] = None
    trend_m_per_yr: Optional[float] = None     # +ve = water table deepening
    n_trend: int = 0
    wells_used: list[WellUsed] = field(default_factory=list)
    source_ids: set[str] = field(default_factory=set)


@dataclass
class PreparedWells:
    """Per-well seasonal medians computed once (batch jobs reuse this)."""
    lat: np.ndarray
    lon: np.ndarray
    pre: np.ndarray
    post: np.ndarray
    trend: np.ndarray
    latest: list                                # list[Optional[date]]
    codes: list[str]
    source_ids: list                            # list[Optional[str]]


def _median_in_window(readings, season: str, since: date) -> Optional[float]:
    vals = [r.depth_to_water_m for r in readings if r.season == season and r.measured_on >= since]
    return float(np.median(vals)) if vals else None


def _trend_m_per_yr(readings, min_years: int, today: date) -> Optional[float]:
    since = today - timedelta(days=int(365.25 * 12))
    pts = [(r.measured_on.year + (r.measured_on.timetuple().tm_yday - 1) / 365.25, r.depth_to_water_m)
           for r in readings if r.season == "pre_monsoon" and r.measured_on >= since]
    if len({int(x) for x, _ in pts}) < min_years:
        return None
    xs, ys = zip(*pts)
    return float(np.polyfit(xs, ys, 1)[0])


def prepare_wells(wells: list[ObservationWell], cfg: StateConfig, today: date) -> PreparedWells:
    wt = cfg.section("water_table")
    since = today - timedelta(days=int(365.25 * wt["window_years"]))
    lat, lon, pre, post, trend, latest, codes, srcs = [], [], [], [], [], [], [], []
    for w in wells:
        lat.append(w.lat)
        lon.append(w.lon)
        pre.append(_median_in_window(w.readings, "pre_monsoon", since))
        post.append(_median_in_window(w.readings, "post_monsoon", since))
        trend.append(_trend_m_per_yr(w.readings, wt["trend_min_years"], today))
        in_window = [r.measured_on for r in w.readings if r.measured_on >= since]
        latest.append(max(in_window) if in_window else None)
        codes.append(w.station_code)
        srcs.append(w.source_id)
    nan = np.nan
    f = lambda xs: np.array([nan if x is None else x for x in xs], dtype=float)  # noqa: E731
    return PreparedWells(np.array(lat, dtype=float), np.array(lon, dtype=float), f(pre), f(post),
                         f(trend), latest, codes, srcs)


def _idw(values: np.ndarray, dist_km: np.ndarray, power: float) -> float:
    w = 1.0 / np.maximum(dist_km, 0.5) ** power
    return float(np.sum(w * values) / np.sum(w))


def summarize_prepared(lat: float, lon: float, pw: PreparedWells, cfg: StateConfig) -> WaterTable:
    wt = cfg.section("water_table")
    radius = float(wt["max_radius_km"])
    out = WaterTable(available=False, reason=None, radius_km=radius)
    if len(pw.lat) == 0:
        out.reason = "no_wells_in_radius"
        return out
    d = haversine_km(lat, lon, pw.lat, pw.lon)
    inside = np.where(d <= radius)[0]
    if inside.size == 0:
        out.reason = "no_wells_in_radius"
        return out
    out.nearest_km = float(np.min(d[inside]))
    has_any = [i for i in inside if not (np.isnan(pw.pre[i]) and np.isnan(pw.post[i]))]
    out.n_wells = len(has_any)
    if not has_any:
        out.reason = "no_recent_readings"
        return out
    pre_idx = np.array([i for i in has_any if not np.isnan(pw.pre[i])], dtype=int)
    post_idx = np.array([i for i in has_any if not np.isnan(pw.post[i])], dtype=int)
    out.n_pre = int(pre_idx.size)

    latest = [pw.latest[i] for i in has_any if pw.latest[i] is not None]
    out.latest_reading_on = max(latest) if latest else None
    if post_idx.size:
        out.post_idw_m = _idw(pw.post[post_idx], d[post_idx], wt["idw_power"])
        out.post_range_m = (float(pw.post[post_idx].min()), float(pw.post[post_idx].max()))
    tr = pw.trend[has_any]
    tr = tr[~np.isnan(tr)]
    if tr.size:
        out.trend_m_per_yr = float(np.median(tr))
        out.n_trend = int(tr.size)

    nearest_order = sorted(has_any, key=lambda i: d[i])[:5]
    out.wells_used = [
        WellUsed(pw.codes[i], float(d[i]),
                 None if np.isnan(pw.pre[i]) else float(pw.pre[i]),
                 None if np.isnan(pw.post[i]) else float(pw.post[i]),
                 pw.latest[i])
        for i in nearest_order
    ]
    out.source_ids = {pw.source_ids[i] for i in has_any if pw.source_ids[i]}

    if pre_idx.size < int(wt["min_wells"]):
        out.reason = "too_few_wells"
        return out
    out.available = True
    out.pre_idw_m = _idw(pw.pre[pre_idx], d[pre_idx], wt["idw_power"])
    out.pre_range_m = (float(pw.pre[pre_idx].min()), float(pw.pre[pre_idx].max()))
    return out


def summarize_wells(lat: float, lon: float, wells: list[ObservationWell], cfg: StateConfig,
                    today: date) -> WaterTable:
    return summarize_prepared(lat, lon, prepare_wells(wells, cfg, today), cfg)
