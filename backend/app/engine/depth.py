"""Estimated drilling-depth range, shown ONLY when nearby records support it.

Method: the 10th-90th percentile of drilled depths of PRODUCTIVE borewells (moderate
or good outcome) within 5 km (else 10 km), provided at least `min_productive_records`
such records exist. No model, no extrapolation: it is a summary of what was
actually drilled nearby. If the evidence is not there the field is reported as
unavailable instead of being invented.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import StateConfig
from .geo import haversine_km, round_to
from .types import PointContext


@dataclass
class DepthRange:
    available: bool
    reason: Optional[str] = None            # insufficient_records | no_records
    low_ft: Optional[float] = None
    high_ft: Optional[float] = None
    median_ft: Optional[float] = None
    n_productive: int = 0
    n_dry: int = 0
    dry_depth_max_ft: Optional[float] = None
    radius_km: Optional[float] = None
    n_required: int = 0
    newest_record_year: Optional[int] = None


def drilling_depth_range(ctx: PointContext, cfg: StateConfig) -> DepthRange:
    dc = cfg.section("depth")
    productive = set(cfg.section("evidence")["productive_outcomes"])
    out = DepthRange(available=False, n_required=int(dc["min_productive_records"]))
    if not ctx.borewells:
        out.reason = "no_records"
        return out

    lat = np.array([b.lat for b in ctx.borewells])
    lon = np.array([b.lon for b in ctx.borewells])
    d = haversine_km(ctx.lat, ctx.lon, lat, lon)

    best_n = 0
    for radius in dc["radii_km"]:
        idx = [i for i, b in enumerate(ctx.borewells) if d[i] <= radius and b.outcome in productive]
        best_n = max(best_n, len(idx))
        if len(idx) >= out.n_required:
            depths = np.array([ctx.borewells[i].depth_ft for i in idx], dtype=float)
            p_lo, p_hi = dc["percentiles"]
            lo, hi = np.percentile(depths, [p_lo, p_hi])
            step = float(dc["round_to_ft"])
            out.available = True
            out.low_ft = float(round_to(lo, step))
            out.high_ft = float(round_to(hi, step))
            out.median_ft = float(round_to(np.median(depths), step))
            out.n_productive = len(idx)
            out.radius_km = float(radius)
            dry = [ctx.borewells[i] for i in range(len(ctx.borewells))
                   if d[i] <= radius and ctx.borewells[i].outcome == "dry"]
            out.n_dry = len(dry)
            out.dry_depth_max_ft = float(max(b.depth_ft for b in dry)) if dry else None
            years = [ctx.borewells[i].drilled_year for i in idx if ctx.borewells[i].drilled_year]
            out.newest_record_year = max(years) if years else None
            return out
    out.reason = "insufficient_records"
    out.n_productive = best_n
    out.radius_km = float(dc["radii_km"][-1])
    return out
