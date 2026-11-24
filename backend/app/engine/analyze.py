"""Orchestrates one location analysis. Pure function of (PointContext, config, today)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .config import INSUFFICIENT, StateConfig
from .confidence import Confidence, compute_confidence
from .depth import DepthRange, drilling_depth_range
from .evidence import LocalEvidence, blend, compute_local_evidence
from .ml import MlModel, MlResult, feature_vector
from .scoring import RegionalResult, build_inputs, regional_stage
from .types import Msg, PointContext, RegionInfo, SourceRef
from .wells import WaterTable, summarize_wells

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_data"
STATUS_OUT = "out_of_coverage"


@dataclass
class AnalysisResult:
    status: str
    lat: float
    lon: float
    data_mode: str
    method_version: str
    klass: str = INSUFFICIENT
    score: Optional[float] = None
    regional_class: str = INSUFFICIENT
    regional: Optional[RegionalResult] = None
    local: Optional[LocalEvidence] = None
    water: Optional[WaterTable] = None
    depth: Optional[DepthRange] = None
    confidence: Optional[Confidence] = None
    ml: Optional[MlResult] = None
    ml_status: str = "not_available"
    region: Optional[RegionInfo] = None
    terrain: dict = field(default_factory=dict)
    rainfall: Optional[dict] = None
    warnings: list[Msg] = field(default_factory=list)
    data_gaps: list[Msg] = field(default_factory=list)
    recommendations: list[Msg] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    sources: dict[str, SourceRef] = field(default_factory=dict)
    data_last_updated: Optional[date] = None
    insufficient_reason: Optional[str] = None


def _rainfall_info(ctx: PointContext, today: date) -> Optional[dict]:
    if not ctx.rainfall_years:
        return None
    recent = [(y, mm) for y, mm in ctx.rainfall_years if y >= today.year - 6]
    recent = sorted(recent)[-5:]
    if len(recent) < 3:
        return None
    mean = sum(mm for _, mm in recent) / len(recent)
    normal = ctx.cell.rainfall_normal_mm if ctx.cell else None
    return {
        "years": [recent[0][0], recent[-1][0]],
        "recent_mean_mm": round(mean, 0),
        "normal_mm": None if normal is None else round(float(normal), 0),
        "anomaly_pct": None if not normal else round((mean - normal) / normal * 100.0, 1),
    }


def _collect_sources(res: AnalysisResult, ctx: PointContext) -> None:
    ids: list[str] = []
    if res.regional:
        ids += [f.source_id for f in res.regional.factors if f.available and f.source_id]
    if res.water:
        ids += sorted(res.water.source_ids)
    if res.local:
        ids += sorted(res.local.source_ids)
    if ctx.region and ctx.region.gw_category_source_id:
        ids.append(ctx.region.gw_category_source_id)
    if ctx.rainfall_source_id and ctx.rainfall_years:
        ids.append(ctx.rainfall_source_id)
    seen, ordered = set(), []
    for i in ids:
        if i not in seen and i in ctx.sources:
            seen.add(i)
            ordered.append(i)
    res.source_ids = ordered
    res.sources = {i: ctx.sources[i] for i in ordered}
    dates = [s.data_last_updated for s in res.sources.values() if s.data_last_updated]
    res.data_last_updated = max(dates) if dates else None


def analyze(ctx: PointContext, cfg: StateConfig, *, today: Optional[date] = None,
            accuracy_m: Optional[float] = None, ml_model: Optional[MlModel] = None) -> AnalysisResult:
    today = today or date.today()
    res = AnalysisResult(status=STATUS_OK, lat=ctx.lat, lon=ctx.lon, data_mode=ctx.data_mode,
                         method_version=cfg.method_version, region=ctx.region)
    if ctx.data_mode == "demo":
        res.warnings.append(Msg("demo_data"))

    # ---- outside the area we hold data for -------------------------------------------
    if not ctx.in_coverage:
        res.status = STATUS_OUT
        res.data_gaps.append(Msg("gap_out_of_coverage"))
        res.recommendations += [Msg("field_study_required"), Msg("consult_hydrogeologist"),
                                Msg("check_permissions"), Msg("seal_unused_borewells")]
        return res

    # ---- stage 1: regional potential ----------------------------------------------------
    water = summarize_wells(ctx.lat, ctx.lon, ctx.wells, cfg, today)
    reg = regional_stage(build_inputs(ctx, cfg, water), cfg)
    res.water, res.regional, res.regional_class = water, reg, reg.klass
    if ctx.cell:
        res.terrain = {"elevation_m": ctx.cell.elevation_m, "cell_id": ctx.cell.cell_id}
    res.rainfall = _rainfall_info(ctx, today)

    # ---- stage 2: local evidence -----------------------------------------------------------
    ev = compute_local_evidence(ctx, cfg)
    depth = drilling_depth_range(ctx, cfg)
    res.local, res.depth = ev, depth

    lith_key = next((f.value for f in reg.factors if f.key == "lithology" and f.available), None)

    # ---- data gaps (always stated explicitly) ------------------------------------------------
    for fk in reg.missing:
        if fk != "water_level":                      # reported separately below with its reason
            res.data_gaps.append(Msg("gap_factor", {"factor": fk}))
    if not water.available:
        res.data_gaps.append(Msg("gap_water_level", {"reason": water.reason or "no_wells_in_radius",
                                                     "radius_km": water.radius_km}))
    if ev.n_borewells_search == 0:
        res.data_gaps.append(Msg("gap_no_borewell_records", {"radius_km": cfg.section("evidence")["borewell_search_max_km"]}))
    elif not ev.used:
        res.data_gaps.append(Msg("gap_few_borewell_records", {"n": ev.n_borewells_search}))
    if not ev.ves_near:
        res.data_gaps.append(Msg("gap_no_geophysics", {"radius_km": cfg.section("evidence")["ves_radius_km"]}))
    if not depth.available:
        res.data_gaps.append(Msg("gap_depth_range", {"reason": depth.reason, "n": depth.n_productive,
                                                    "n_required": depth.n_required,
                                                    "radius_km": depth.radius_km}))
    if not (ctx.region and ctx.region.gw_category):
        res.data_gaps.append(Msg("gap_gw_category"))

    # ---- insufficient regional data => grey, no class, no confidence -------------------------------
    if reg.status != "ok":
        res.status = STATUS_INSUFFICIENT
        res.insufficient_reason = reg.reason
        res.recommendations += [Msg("field_study_required"), Msg("consult_hydrogeologist"),
                                Msg("check_permissions"), Msg("seal_unused_borewells")]
        _collect_sources(res, ctx)
        return res

    # ---- final score & class --------------------------------------------------------------------------
    res.score = blend(reg.score, ev, cfg)
    res.klass = cfg.classify(res.score)

    # optional ML second opinion (only if a gated model was loaded)
    if ml_model is not None:
        res.ml = ml_model.predict(feature_vector(reg.factors, cfg), cfg.class_rank(res.klass))
        res.ml_status = "available"

    res.confidence = compute_confidence(
        coverage=reg.coverage, regional_score=reg.score, final_score=res.score, evidence=ev, water=water,
        cfg=cfg, ml_agrees=None if res.ml is None else res.ml.agrees, today=today)

    # ---- warnings ---------------------------------------------------------------------------------------------
    evc = cfg.section("evidence")
    if lith_key in cfg.hard_rock_lithologies:
        res.warnings.append(Msg("hard_rock_variability"))
    if ev.used and ev.n_borewells_radius >= evc["disagreement_min_n"] and ev.mean_score is not None:
        diff = ev.mean_score - reg.score
        if abs(diff) >= evc["disagreement_threshold"]:
            res.warnings.append(Msg("local_better_than_regional" if diff > 0 else "local_worse_than_regional",
                                    {"n": ev.n_borewells_radius, "radius_km": ev.radius_km}))
    if res.ml is not None and res.ml.agrees is False:
        res.warnings.append(Msg("ml_disagrees", {"p": round(res.ml.probability * 100)}))
    thr = cfg.section("water_table")["decline_threshold_m_per_yr"]
    if water.trend_m_per_yr is not None and water.trend_m_per_yr >= thr:
        res.warnings.append(Msg("declining_water_levels", {"rate_m": round(water.trend_m_per_yr, 2),
                                                           "n": water.n_trend}))
    if accuracy_m is not None and accuracy_m > 50:
        res.warnings.append(Msg("low_location_accuracy", {"accuracy_m": round(accuracy_m)}))
    cat = ctx.region.gw_category if ctx.region else None
    if cat in ("over_exploited", "critical", "saline"):
        res.warnings.append(Msg(f"gw_{cat}", {"year": ctx.region.gw_category_year}))
    if res.confidence.capped:
        res.warnings.append(Msg("confidence_capped"))

    # ---- recommendations -------------------------------------------------------------------------------------------
    rec = res.recommendations
    rec.append(Msg("consult_hydrogeologist"))
    rec.append(Msg("verify_with_geophysics_on_site" if ev.ves_near else "geophysical_survey"))
    if res.klass in ("low", "very_low"):
        rec += [Msg("alternatives_low_potential"), Msg("dont_drill_deeper_blindly")]
    elif lith_key in cfg.hard_rock_lithologies:
        rec.append(Msg("siting_matters"))
    rec += [Msg("check_permissions"), Msg("seal_unused_borewells")]

    _collect_sources(res, ctx)
    return res
