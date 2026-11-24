"""End-to-end engine behaviour on the synthetic demo dataset + the 'never fabricate' rules."""
import json
from dataclasses import asdict
from datetime import date

import pytest

from app.engine import analyze
from app.engine.ml import feature_vector, load_model, train_model
from app.engine.scoring import regional_for_point
from app.engine.types import Radii
from app.engine.wells import prepare_wells
from tests.conftest import make_bw, make_ctx

R = Radii()


def test_out_of_coverage_is_grey_and_has_no_numbers(demo_repo, cfg, today):
    for lat, lon in [(17.9689, 79.5941), (10.0, 80.0)]:        # Warangal (outside demo area), open sea
        r = analyze(demo_repo.point_context(lat, lon, R), cfg, today=today)
        assert r.status == "out_of_coverage" and r.klass == "insufficient_data"
        assert r.score is None and r.confidence is None and r.depth is None and r.water is None
        assert any(m.code == "gap_out_of_coverage" for m in r.data_gaps)


def test_demo_results_are_always_flagged(demo_repo, cfg, today):
    r = analyze(demo_repo.point_context(17.6812, 77.607, R), cfg, today=today)
    assert r.data_mode == "demo" and r.warnings[0].code == "demo_data"
    assert all(s.is_demo for s in r.sources.values())


def test_production_mode_has_no_demo_warning(cfg, today):
    r = analyze(make_ctx(), cfg, today=today)
    assert r.data_mode == "production" and all(m.code != "demo_data" for m in r.warnings)


def test_depth_range_never_invented(demo_repo, cfg, today):
    """Wherever a depth range is shown, enough productive records must stand behind it."""
    import random
    random.seed(3)
    shown = hidden = 0
    for _ in range(120):
        lat, lon = random.uniform(17.02, 18.28), random.uniform(77.57, 79.03)
        r = analyze(demo_repo.point_context(lat, lon, R), cfg, today=today)
        if r.depth.available:
            shown += 1
            assert r.depth.n_productive >= r.depth.n_required and r.depth.low_ft <= r.depth.high_ft
        else:
            hidden += 1
            assert r.depth.low_ft is None and r.depth.high_ft is None
            assert any(m.code == "gap_depth_range" for m in r.data_gaps)
    assert shown and hidden            # the demo exercises both branches


def test_every_result_lists_sources_and_dates(demo_repo, cfg, today):
    r = analyze(demo_repo.point_context(17.385, 78.4867, R), cfg, today=today)
    assert r.source_ids and r.data_last_updated == date(2026, 6, 30)


def test_gaps_are_reported_not_hidden(cfg, today):
    r = analyze(make_ctx(wells=[]), cfg, today=today)
    codes = [m.code for m in r.data_gaps]
    assert "gap_water_level" in codes and "gap_no_borewell_records" in codes and "gap_no_geophysics" in codes


def test_insufficient_regional_data_gives_no_class_and_no_confidence(cfg, today):
    r = analyze(make_ctx(lithology=None), cfg, today=today)
    assert r.status == "insufficient_data" and r.score is None and r.confidence is None
    assert [m.code for m in r.recommendations][0] == "field_study_required"


def test_local_dry_wells_override_optimistic_region(cfg, today):
    base = analyze(make_ctx(), cfg, today=today)
    dry = analyze(make_ctx(borewells=[make_bw(i, outcome="dry", lat=17.5 + i * 1e-4) for i in range(8)]), cfg, today=today)
    assert dry.score < base.score and dry.regional.score == base.regional.score
    assert any(m.code == "local_worse_than_regional" for m in dry.warnings)


def test_analysis_is_deterministic(demo_repo, cfg, today):
    a = analyze(demo_repo.point_context(17.62, 78.09, R), cfg, today=today)
    b = analyze(demo_repo.point_context(17.62, 78.09, R), cfg, today=today)
    assert a.score == b.score and a.klass == b.klass and a.confidence.score == b.confidence.score


def test_map_class_matches_report_regional_class(demo_repo, cfg, today):
    """The colour on the map and the report's 'regional class' must come from the same code path."""
    cells = demo_repo.potential_cells(today)
    for gc, reg in cells[::397][:12]:
        lat, lon = gc.centroid
        r = analyze(demo_repo.point_context(lat, lon, R), cfg, today=today)
        assert r.regional_class == reg.klass and r.regional.score == reg.score


def test_ml_model_is_gated(demo_repo, cfg, today, tmp_path):
    assert load_model(tmp_path, cfg, "demo") is None                      # nothing trained => not available
    pw = prepare_wells(demo_repo.ds.wells, cfg, today)
    rows = []
    for lat, lon, outcome in demo_repo.training_points():
        gc = demo_repo._cell_at(lat, lon)
        reg = regional_for_point(lat=lat, lon=lon, cell=gc.cell, lithology=demo_repo._geo.lookup(lat, lon),
                                 aquifer=demo_repo._aq.lookup(lat, lon), soil=demo_repo._soil.lookup(lat, lon),
                                 prepared_wells=pw, cfg=cfg)
        rows.append((feature_vector(reg.factors, cfg), int(outcome in ("moderate", "good")),
                     (int(lat / 0.045), int(lon / 0.045))))
    meta = train_model(rows, cfg, "demo", tmp_path)
    assert meta["trained_on_demo"] is True and 0.5 < meta["cv_auc"] <= 1.0
    # a demo-trained model must NEVER be served in production mode
    assert load_model(tmp_path, cfg, "production") is None
    if meta["passes_gate"]:
        m = load_model(tmp_path, cfg, "demo")
        assert m is not None
        res = analyze(demo_repo.point_context(17.62, 78.09, R), cfg, today=today, ml_model=m)
        assert res.ml is not None and 0 <= res.ml.probability <= 1 and res.ml.trained_on_demo


def test_result_is_json_serialisable_after_presentation(demo_repo, cfg, today):
    r = analyze(demo_repo.point_context(17.62, 78.09, R), cfg, today=today)
    json.dumps(asdict(r), default=str)
