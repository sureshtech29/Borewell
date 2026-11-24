"""Build the training table for the optional statistical model from a repository's borewell records.

Features are the REGIONAL-stage factor scores at each borewell (never the local-evidence blend), the label is
"productive" (outcome in ml.positive_outcomes) vs not, and every row carries a spatial block id so that
cross-validation never tests on a block it trained on (neighbouring borewells are highly correlated).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Iterable, Protocol

from .config import StateConfig
from .geo import KM_PER_DEG_LAT
from .ml import feature_vector
from .scoring import build_inputs, regional_stage
from .types import PointContext, Radii
from .wells import summarize_wells


class _Repo(Protocol):
    def training_points(self) -> Iterable[tuple[float, float, str]]: ...
    def point_context(self, lat: float, lon: float, radii: Radii) -> PointContext: ...


def block_id(lat: float, lon: float, block_km: float) -> tuple[int, int]:
    dlat = block_km / KM_PER_DEG_LAT
    dlon = block_km / (KM_PER_DEG_LAT * max(0.2, math.cos(math.radians(lat))))
    return int(math.floor(lat / dlat)), int(math.floor(lon / dlon))


def build_training_rows(repo: _Repo, cfg: StateConfig, today: date, radii: Radii | None = None):
    """-> (rows, stats). rows = [(feature_vector, label, block_id)]."""
    ml = cfg.section("ml")
    positive = set(ml["positive_outcomes"])
    radii = radii or Radii(wells_km=float(cfg.section("water_table")["max_radius_km"]), borewells_km=0.0,
                           ves_km=0.0, rainfall_years=1)
    rows, stats = [], {"records": 0, "used": 0, "outside_coverage": 0, "insufficient_regional": 0, "unknown_outcome": 0}
    known = {"dry", "low", "moderate", "good"}
    for lat, lon, outcome in repo.training_points():
        stats["records"] += 1
        if outcome not in known:
            stats["unknown_outcome"] += 1
            continue
        ctx = repo.point_context(lat, lon, radii)
        if not ctx.in_coverage:
            stats["outside_coverage"] += 1
            continue
        reg = regional_stage(build_inputs(ctx, cfg, summarize_wells(lat, lon, ctx.wells, cfg, today)), cfg)
        if reg.status != "ok":
            stats["insufficient_regional"] += 1
            continue
        rows.append((feature_vector(reg.factors, cfg), 1 if outcome in positive else 0,
                     block_id(lat, lon, float(ml["block_size_km"]))))
        stats["used"] += 1
    return rows, stats
