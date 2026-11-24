"""Regional (map-stage) groundwater potential index: weighted overlay.

score = sum(weight_i * score_i) / sum(weight_i)  over the factors that are
APPLICABLE and have DATA. Factors without data are dropped (never guessed) and
reduce `coverage`, which in turn reduces confidence and can force the result
to "insufficient data".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .config import INSUFFICIENT, StateConfig
from .types import ClassifiedUnit, FeatureCell, PointContext
from .wells import PreparedWells, WaterTable, summarize_prepared


@dataclass
class FactorInput:
    value: Any
    source_id: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class FactorResult:
    key: str
    kind: str                       # categorical | numeric
    applicable: bool
    available: bool
    weight: float
    effective_weight: float = 0.0   # re-normalised weight actually used
    value: Any = None               # raw number, or class key for categorical
    unit: Optional[str] = None
    score: Optional[float] = None   # 0..100
    source_id: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class RegionalResult:
    status: str                     # ok | insufficient_data
    score: Optional[float]
    klass: str
    coverage: float
    factors: list[FactorResult]
    missing: list[str]              # applicable factors without data
    reason: Optional[str] = None    # why insufficient


def interp(points: list[list[float]], x: float) -> float:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return float(np.interp(x, xs, ys))      # clamps outside the range


def _num(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def build_inputs(ctx: PointContext, cfg: StateConfig, wt: WaterTable) -> dict[str, FactorInput]:
    """Map a PointContext to {factor_key: FactorInput} for the factors that have data."""
    out: dict[str, FactorInput] = {}
    for key, unit in (("lithology", ctx.lithology), ("aquifer", ctx.aquifer), ("soil", ctx.soil)):
        if unit is not None:
            out[key] = FactorInput(unit.class_key, unit.source_id, {"name": unit.name})
    if ctx.cell is not None:
        for key, f in cfg.factors.items():
            if f["kind"] == "numeric" and key != "water_level":
                v = _num(getattr(ctx.cell, f["input"], None))
                if v is not None:
                    out[key] = FactorInput(v, ctx.cell.source_ids.get(key))
    if wt.available and wt.pre_idw_m is not None:
        src = sorted(wt.source_ids)[0] if wt.source_ids else None
        out["water_level"] = FactorInput(wt.pre_idw_m, src, {"n_wells": wt.n_pre, "nearest_km": wt.nearest_km})
    return out


def regional_stage(inputs: dict[str, FactorInput], cfg: StateConfig) -> RegionalResult:
    rcfg = cfg.section("regional")
    lith = inputs.get("lithology")
    lith_key = lith.value if lith else None

    results: list[FactorResult] = []
    for key, f in cfg.factors.items():
        na_list = f.get("not_applicable_for_lithology", [])
        applicable = not (lith_key is not None and lith_key in na_list)
        fr = FactorResult(key=key, kind=f["kind"], applicable=applicable, available=False,
                          weight=float(f["weight"]), unit=f.get("unit"))
        inp = inputs.get(key)
        if applicable and inp is not None and inp.value is not None:
            if f["kind"] == "categorical":
                item = f["classes"].get(str(inp.value))
                if item is not None:
                    fr.available, fr.value, fr.score = True, str(inp.value), float(item["score"])
            else:
                v = _num(inp.value)
                if v is not None:
                    fr.available, fr.value, fr.score = True, v, interp(f["points"], v)
            if fr.available:
                fr.source_id = inp.source_id
                fr.extra = dict(inp.extra)
        results.append(fr)

    applicable_w = sum(r.weight for r in results if r.applicable)
    avail_w = sum(r.weight for r in results if r.applicable and r.available)
    coverage = (avail_w / applicable_w) if applicable_w > 0 else 0.0
    for r in results:
        r.effective_weight = (r.weight / avail_w) if (r.applicable and r.available and avail_w > 0) else 0.0
    missing = [r.key for r in results if r.applicable and not r.available]

    missing_required = [k for k in rcfg["required_factors"]
                        if not next(r for r in results if r.key == k).available]
    if missing_required:
        return RegionalResult("insufficient_data", None, INSUFFICIENT, coverage, results, missing,
                              reason="missing_required:" + ",".join(missing_required))
    if coverage < float(rcfg["min_coverage"]):
        return RegionalResult("insufficient_data", None, INSUFFICIENT, coverage, results, missing,
                              reason="low_coverage")

    score = sum(r.effective_weight * r.score for r in results if r.available and r.score is not None)
    score = float(round(score, 2))
    return RegionalResult("ok", score, cfg.classify(score), coverage, results, missing)


def regional_for_point(*, lat: float, lon: float, cell: Optional[FeatureCell],
                       lithology: Optional[ClassifiedUnit], aquifer: Optional[ClassifiedUnit],
                       soil: Optional[ClassifiedUnit], prepared_wells: PreparedWells,
                       cfg: StateConfig) -> RegionalResult:
    """Regional stage for one point/cell without building a full PointContext.

    Shared by the map pre-computation (all cells), ML training and the per-point
    analysis so the map colour and the report's regional class can never diverge.
    """
    wt = summarize_prepared(lat, lon, prepared_wells, cfg)
    ctx = PointContext(lat=lat, lon=lon, cell=cell, lithology=lithology, aquifer=aquifer, soil=soil)
    return regional_stage(build_inputs(ctx, cfg, wt), cfg)
