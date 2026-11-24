"""Engine result -> JSON-ready dict with English + Telugu text (single source for API, UI and PDF)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from . import i18n
from .engine.analyze import AnalysisResult
from .engine.config import INSUFFICIENT, StateConfig
from .engine.geo import m_to_ft
from .engine.types import Msg, RegionInfo, SourceRef


def source_to_dict(s: SourceRef) -> dict:
    return {
        "id": s.source_id,
        "name": {"en": s.name_en, "te": s.name_te or s.name_en},
        "publisher": s.publisher, "layer_kind": s.layer_kind, "url": s.url, "license": s.license,
        "retrieved_on": s.retrieved_on.isoformat() if s.retrieved_on else None,
        "data_last_updated": s.data_last_updated.isoformat() if s.data_last_updated else None,
        "is_demo": s.is_demo, "notes": s.notes,
    }


def _msgs(items: list[Msg], cfg: StateConfig) -> list[dict]:
    out = []
    for m in items:
        params = dict(m.params)
        if m.code == "gap_factor":
            params["factor"] = cfg.factors[params["factor"]]["label"]
        out.append({"code": m.code, "text": i18n.render(m.code, params)})
    return out


def _region(reg: Optional[RegionInfo]) -> Optional[dict]:
    if reg is None:
        return None

    def pair(en, te):
        return None if not en else {"en": en, "te": te or en}

    gw = None
    if reg.gw_category:
        gw = {"key": reg.gw_category, "label": i18n.GW_CATEGORY.get(reg.gw_category), "year": reg.gw_category_year}
    return {"state": {"en": reg.state_en, "te": reg.state_te or reg.state_en},
            "district": pair(reg.district_en, reg.district_te), "mandal": pair(reg.mandal_en, reg.mandal_te),
            "village": pair(reg.village_en, reg.village_te), "method": reg.method,
            "nearest_place_km": None if reg.nearest_place_km is None else round(reg.nearest_place_km, 1),
            "gw_category": gw}


def _display(f, cfg: StateConfig) -> Optional[dict]:
    if not (f.applicable and f.available):
        return None
    if f.kind == "categorical":
        return cfg.categorical_label(f.key, f.value)
    v, u = float(f.value), f.unit
    if u == "deg":
        s = f"{v:.1f} °"
        return {"en": s, "te": s}
    if u == "km/km2":
        s = f"{v:.2f} km/km²"
        return {"en": s, "te": s}
    if u == "mm":
        return {"en": f"{v:.0f} mm", "te": f"{v:.0f} మి.మీ."}
    if u == "m bgl":
        return {"en": f"{v:.1f} m ({m_to_ft(v):.0f} ft)", "te": f"{v:.1f} మీ. ({m_to_ft(v):.0f} అడుగులు)"}
    if u == "m":
        return {"en": f"{v:+.0f} m", "te": f"{v:+.0f} మీ."}
    return {"en": f"{v:g}", "te": f"{v:g}"}


def _factors(res: AnalysisResult, cfg: StateConfig) -> list[dict]:
    if res.regional is None:
        return []
    out = []
    for f in res.regional.factors:
        out.append({
            "key": f.key, "label": cfg.factors[f.key]["label"], "kind": f.kind,
            "applicable": f.applicable, "available": f.available,
            "value": f.value if f.kind == "categorical" else (None if f.value is None else round(float(f.value), 3)),
            "unit": f.unit, "display": _display(f, cfg),
            "score": None if f.score is None else round(f.score, 1),
            "weight": round(f.weight, 3), "effective_weight": round(f.effective_weight, 3),
            "source_id": f.source_id,
        })
    return out


def _range(pair, to_ft=True):
    if pair is None:
        return None
    return {"range_m": [round(pair[0], 1), round(pair[1], 1)],
            "range_ft": [round(m_to_ft(pair[0])), round(m_to_ft(pair[1]))]}


def _water(res: AnalysisResult) -> Optional[dict]:
    w = res.water
    if w is None:
        return None
    pre = _range(w.pre_range_m)
    if pre and w.pre_idw_m is not None:
        pre.update(estimate_m=round(w.pre_idw_m, 1), estimate_ft=round(m_to_ft(w.pre_idw_m)))
    post = _range(w.post_range_m)
    if post and w.post_idw_m is not None:
        post.update(estimate_m=round(w.post_idw_m, 1), estimate_ft=round(m_to_ft(w.post_idw_m)))
    return {
        "available": w.available, "reason": w.reason, "radius_km": w.radius_km, "n_wells": w.n_pre,
        "nearest_km": None if w.nearest_km is None else round(w.nearest_km, 1),
        "pre_monsoon": pre if w.available else None, "post_monsoon": post if w.available else None,
        "trend_m_per_yr": None if w.trend_m_per_yr is None else round(w.trend_m_per_yr, 2),
        "latest_reading_on": w.latest_reading_on.isoformat() if w.latest_reading_on else None,
        "wells": [{"station_code": u.station_code, "distance_km": round(u.distance_km, 1),
                   "pre_monsoon_m": None if u.pre_monsoon_m is None else round(u.pre_monsoon_m, 1),
                   "post_monsoon_m": None if u.post_monsoon_m is None else round(u.post_monsoon_m, 1)}
                  for u in w.wells_used] if w.available else [],
        "note": i18n.MESSAGES["water_table_note"],
    }


def _depth(res: AnalysisResult) -> Optional[dict]:
    d = res.depth
    if d is None:
        return None
    return {"available": d.available, "reason": d.reason, "low_ft": d.low_ft, "high_ft": d.high_ft,
            "median_ft": d.median_ft, "n_productive": d.n_productive, "n_dry": d.n_dry,
            "dry_depth_max_ft": d.dry_depth_max_ft, "radius_km": d.radius_km, "n_required": d.n_required,
            "newest_record_year": d.newest_record_year, "note": i18n.MESSAGES["depth_note"]}


def _local(res: AnalysisResult) -> Optional[dict]:
    ev = res.local
    if ev is None:
        return None
    counts = [{"key": k, "count": int(ev.outcome_counts.get(k, 0)), "label": i18n.LABELS[f"outcome.{k}"]}
              for k in ("dry", "low", "moderate", "good")]
    return {
        "used": ev.used, "radius_km": ev.radius_km, "n_records": ev.n_borewells_radius,
        "n_records_wider": ev.n_borewells_search,
        "nearest_record_km": None if ev.nearest_borewell_km is None else round(ev.nearest_borewell_km, 1),
        "outcomes": counts, "effective_n": round(ev.effective_n, 2),
        "local_score": None if ev.mean_score is None else round(ev.mean_score, 1),
        "newest_record_year": ev.newest_record_year,
        "ves": [{"distance_km": round(v.distance_km, 2), "method": v.method, "survey_year": v.survey_year,
                 "suitability": v.suitability, "suitability_label": i18n.LABELS[f"suitability.{v.suitability}"],
                 "weathered_thickness_m": v.weathered_thickness_m, "fracture_zone_top_m": v.fracture_zone_top_m,
                 "fracture_zone_bottom_m": v.fracture_zone_bottom_m} for v in ev.ves_near],
    }


def _confidence(res: AnalysisResult) -> Optional[dict]:
    c = res.confidence
    if c is None:
        return None
    return {"level": c.level, "label": i18n.LABELS[f"conf_{c.level}"], "score": c.score, "capped": c.capped,
            "components": [{"key": x.key, "label": i18n.LABELS[f"conf_component.{x.key}"],
                            "value": round(x.value, 2), "weight": x.weight} for x in c.components],
            "note": i18n.MESSAGES["confidence_note"]}


def _ml(res: AnalysisResult) -> dict:
    if res.ml is None:
        return {"status": "not_available", "text": i18n.render("ml.not_available")}
    m = res.ml
    text = i18n.render("ml.available", {"p": round(m.probability * 100), "auc": round(m.cv_auc, 2), "n": m.n_train})
    if m.trained_on_demo:
        extra = i18n.render("ml.demo_trained")
        text = {k: f"{text[k]} {extra[k]}" for k in text}
    return {"status": "available", "probability": m.probability, "cv_auc": m.cv_auc, "n_train": m.n_train,
            "trained_on_demo": m.trained_on_demo, "agrees": m.agrees, "text": text}


def present(res: AnalysisResult, cfg: StateConfig, *, accuracy_m: Optional[float] = None,
            now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    reason_key = (res.insufficient_reason or "").split(":")[0]
    status_title = None
    if res.status == "out_of_coverage":
        status_title = i18n.LABELS["status.out_of_coverage"]
    elif res.status == "insufficient_data":
        status_title = i18n.LABELS["status.insufficient_data"]
    grey = INSUFFICIENT
    return {
        "status": res.status, "status_title": status_title,
        "data_mode": res.data_mode, "is_demo": res.data_mode == "demo",
        "location": {"lat": res.lat, "lon": res.lon, "accuracy_m": accuracy_m, "region": _region(res.region)},
        "potential": {
            "class": res.klass, "label": cfg.class_label(res.klass), "color": cfg.class_color(res.klass),
            "score": res.score,
            "regional_class": res.regional_class, "regional_label": cfg.class_label(res.regional_class),
            "regional_color": cfg.class_color(res.regional_class),
            "regional_score": None if res.regional is None else res.regional.score,
            "coverage": None if res.regional is None else round(res.regional.coverage, 2),
            "insufficient_reason": i18n.render(f"insufficient.{reason_key}") if reason_key in ("low_coverage", "missing_required") else None,
            "note": i18n.MESSAGES["potential_note"],
        },
        "confidence": _confidence(res),
        "factors": _factors(res, cfg),
        "terrain": res.terrain,
        "rainfall": res.rainfall,
        "water_table": _water(res),
        "drilling_depth": _depth(res),
        "local_evidence": _local(res),
        "statistical_model": _ml(res) if res.status == "ok" else {"status": "not_available", "text": i18n.render("ml.not_available")},
        "warnings": _msgs(res.warnings, cfg),
        "data_gaps": _msgs(res.data_gaps, cfg),
        "recommendations": _msgs(res.recommendations, cfg),
        "sources": [source_to_dict(s) for s in res.sources.values()],
        "data_last_updated": res.data_last_updated.isoformat() if res.data_last_updated else None,
        "method": {"version": res.method_version, "name": cfg.method_name},
        "disclaimer": i18n.MESSAGES["disclaimer"],
        "generated_at": now.isoformat(timespec="seconds"),
    }
