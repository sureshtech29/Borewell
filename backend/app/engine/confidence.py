"""Transparent confidence score (0..1) built from how much real evidence exists.

Confidence is NOT the probability that a borewell will yield water. It describes how
well-supported the potential class is by the data that was actually available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .config import StateConfig
from .evidence import LocalEvidence
from .wells import WaterTable


@dataclass
class ConfComponent:
    key: str
    value: float          # 0..1
    weight: float
    detail: dict = field(default_factory=dict)


@dataclass
class Confidence:
    score: float
    level: str            # low | medium | high
    components: list[ConfComponent]
    capped: bool = False  # True if a cap lowered the level


def _recency(latest: Optional[date], today: date, cc: dict) -> tuple[float, Optional[float]]:
    if latest is None:
        return 0.0, None
    age = (today - latest).days / 365.25
    for years, val in cc["recency_bands_years"]:
        if age <= years:
            return float(val), age
    return float(cc["recency_floor"]), age


def compute_confidence(*, coverage: float, regional_score: float, final_score: float,
                       evidence: LocalEvidence, water: WaterTable, cfg: StateConfig,
                       ml_agrees: Optional[bool] = None, today: date) -> Confidence:
    cc = cfg.section("confidence")
    w = cc["weights"]

    local_support = min(1.0, evidence.effective_n / float(cc["local_n_full"])) if evidence.used else 0.0

    if water.available:
        n_part = min(1.0, water.n_pre / float(cc["wells_full"]))
        near = water.nearest_km if water.nearest_km is not None else 99.0
        prox = 1.0 if near <= cc["wells_near_km"] else (0.5 if near <= cc["wells_far_km"] else 0.25)
        wl_support = n_part * prox
    else:
        wl_support = 0.0

    geophysics = 1.0 if evidence.ves_near else 0.0

    recency, age = _recency(water.latest_reading_on, today, cc)

    if evidence.used and evidence.mean_score is not None:
        consistency = max(0.0, 1.0 - abs(regional_score - evidence.mean_score) / 50.0)
        if ml_agrees is False:
            consistency *= 0.7
    else:
        consistency = 0.0

    comps = [
        ConfComponent("coverage", float(coverage), w["coverage"]),
        ConfComponent("local_support", float(local_support), w["local_support"],
                      {"effective_n": round(evidence.effective_n, 2)}),
        ConfComponent("water_level_support", float(wl_support), w["water_level_support"],
                      {"n_wells": water.n_pre, "nearest_km": water.nearest_km}),
        ConfComponent("geophysics", float(geophysics), w["geophysics"]),
        ConfComponent("recency", float(recency), w["recency"], {"age_years": None if age is None else round(age, 1)}),
        ConfComponent("consistency", float(consistency), w["consistency"]),
    ]
    score = float(round(sum(c.value * c.weight for c in comps), 3))

    lv = cc["levels"]
    level = "low" if score < lv["low_below"] else ("high" if score >= lv["high_from"] else "medium")
    capped = False
    if level == "high" and evidence.effective_n < float(cc["high_requires_effective_n"]):
        level, capped = "medium", True
    return Confidence(score=score, level=level, components=comps, capped=capped)
