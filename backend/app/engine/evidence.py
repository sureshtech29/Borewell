"""Local evidence: nearby historical borewell outcomes and geophysical (VES) surveys.

The regional score acts as a prior worth `prior_strength` pseudo-records. Each nearby
record adds a distance-weighted observation. With few records the result stays close
to the regional score; with many it is dominated by what actually happened nearby
(an empirical-Bayes style shrinkage). This keeps the output honest in both
data-rich and data-poor areas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .config import StateConfig
from .geo import haversine_km
from .types import PointContext


@dataclass
class VesNear:
    survey_id: int
    distance_km: float
    method: str
    suitability: str
    survey_year: Optional[int]
    weathered_thickness_m: Optional[float]
    fracture_zone_top_m: Optional[float]
    fracture_zone_bottom_m: Optional[float]
    note: Optional[str]
    source_id: Optional[str]


@dataclass
class LocalEvidence:
    used: bool = False
    radius_km: float = 0.0
    n_borewells_radius: int = 0                # inside the evidence radius
    n_borewells_search: int = 0                # inside the wider search radius
    nearest_borewell_km: Optional[float] = None
    outcome_counts: dict = field(default_factory=dict)
    borewell_weight: float = 0.0
    ves_weight: float = 0.0
    effective_n: float = 0.0
    mean_score: Optional[float] = None
    newest_record_year: Optional[int] = None
    ves_near: list[VesNear] = field(default_factory=list)
    source_ids: set[str] = field(default_factory=set)


def compute_local_evidence(ctx: PointContext, cfg: StateConfig) -> LocalEvidence:
    ev = cfg.section("evidence")
    out = LocalEvidence(radius_km=float(ev["borewell_radius_km"]))
    scores = ev["outcome_scores"]

    num = 0.0
    den = 0.0

    # ---- borewell records -----------------------------------------------------
    if ctx.borewells:
        lat = np.array([b.lat for b in ctx.borewells])
        lon = np.array([b.lon for b in ctx.borewells])
        d = haversine_km(ctx.lat, ctx.lon, lat, lon)
        search = d <= float(ev["borewell_search_max_km"])
        out.n_borewells_search = int(search.sum())
        if search.any():
            out.nearest_borewell_km = float(d[search].min())
        counts = {"dry": 0, "low": 0, "moderate": 0, "good": 0}
        years = []
        for b, dist in zip(ctx.borewells, d):
            if dist > out.radius_km:
                continue
            w = 1.0 / (1.0 + dist / float(ev["distance_decay_km"]))
            acc = b.location_accuracy_m
            if acc is not None and acc > ev["max_location_accuracy_m"]:
                w *= 0.5
            s = scores.get(b.outcome)
            if s is None:
                continue
            num += w * s
            den += w
            out.borewell_weight += w
            out.n_borewells_radius += 1
            counts[b.outcome] = counts.get(b.outcome, 0) + 1
            if b.drilled_year:
                years.append(b.drilled_year)
            if b.source_id:
                out.source_ids.add(b.source_id)
        out.outcome_counts = counts
        out.newest_record_year = max(years) if years else None

    # ---- geophysical surveys ----------------------------------------------------
    for v in ctx.ves:
        dist = float(haversine_km(ctx.lat, ctx.lon, v.lat, v.lon))
        if dist > float(ev["ves_radius_km"]):
            continue
        s = ev["ves_scores"].get(v.suitability)
        if s is None:
            continue
        w = float(ev["ves_weight"]) / (1.0 + dist / float(ev["ves_decay_km"]))
        num += w * s
        den += w
        out.ves_weight += w
        out.ves_near.append(VesNear(v.survey_id, dist, v.method, v.suitability, v.survey_year,
                                    v.weathered_thickness_m, v.fracture_zone_top_m,
                                    v.fracture_zone_bottom_m, v.note, v.source_id))
        if v.source_id:
            out.source_ids.add(v.source_id)
    out.ves_near.sort(key=lambda x: x.distance_km)

    out.effective_n = den
    if den >= float(ev["min_effective_n"]):
        out.used = True
        out.mean_score = num / den
    return out


def blend(regional_score: float, evidence: LocalEvidence, cfg: StateConfig) -> float:
    """Posterior-style blend of the regional prior and the local observations."""
    if not evidence.used or evidence.mean_score is None:
        return regional_score
    k = float(cfg.section("evidence")["prior_strength"])
    n = evidence.effective_n
    return float(round((k * regional_score + n * evidence.mean_score) / (k + n), 2))
