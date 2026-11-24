import copy

import pytest

from app.engine.config import ConfigError, StateConfig
from app.engine.scoring import FactorInput, build_inputs, interp, regional_stage
from app.engine.wells import summarize_wells
from tests.conftest import make_cell, make_ctx


def run(cfg, ctx, today):
    wt = summarize_wells(ctx.lat, ctx.lon, ctx.wells, cfg, today)
    return regional_stage(build_inputs(ctx, cfg, wt), cfg)


def test_config_weights_sum_to_one(cfg):
    assert abs(sum(f["weight"] for f in cfg.factors.values()) - 1.0) < 1e-9


def test_bad_weights_rejected(cfg):
    raw = copy.deepcopy(cfg.raw)
    raw["factors"]["slope"]["weight"] = 0.5
    with pytest.raises(ConfigError):
        StateConfig(raw)


def test_interp_is_clamped_and_monotone(cfg):
    pts = cfg.factors["slope"]["points"]
    assert interp(pts, -5) == interp(pts, 0) == 100
    assert interp(pts, 500) == 0
    vals = [interp(pts, x) for x in range(0, 60)]
    assert all(a >= b for a, b in zip(vals, vals[1:]))          # steeper => never better


def test_full_data_gives_class_and_full_coverage(cfg, today):
    r = run(cfg, make_ctx(), today)
    assert r.status == "ok" and r.coverage == pytest.approx(1.0)
    assert 0 < r.score < 100 and r.klass in ("high", "moderate", "low", "very_low")
    assert sum(f.effective_weight for f in r.factors) == pytest.approx(1.0)


def test_better_terrain_scores_higher(cfg, today):
    good = make_ctx(cell=make_cell(slope_deg=0.5, drainage_density=0.8, lineament_density=2.0, tpi_m=-10))
    bad = make_ctx(cell=make_cell(slope_deg=20, drainage_density=5, lineament_density=0.1, tpi_m=40))
    assert run(cfg, good, today).score > run(cfg, bad, today).score + 20


def test_missing_factor_is_dropped_not_guessed(cfg, today):
    ctx = make_ctx(wells=[])                                    # no water-level data
    r = run(cfg, ctx, today)
    assert r.status == "ok"
    assert r.coverage == pytest.approx(0.85)
    wl = next(f for f in r.factors if f.key == "water_level")
    assert not wl.available and wl.score is None and wl.effective_weight == 0
    assert "water_level" in r.missing


def test_lithology_is_required(cfg, today):
    r = run(cfg, make_ctx(lithology=None), today)
    assert r.status == "insufficient_data" and r.klass == "insufficient_data" and r.score is None
    assert r.reason.startswith("missing_required")


def test_low_coverage_means_insufficient(cfg, today):
    ctx = make_ctx(cell=None, aquifer=None, soil=None, wells=[])   # only lithology left
    r = run(cfg, ctx, today)
    assert r.status == "insufficient_data" and r.reason == "low_coverage" and r.score is None


def test_lineament_not_applicable_on_alluvium(cfg, today):
    from app.engine.types import ClassifiedUnit
    ctx = make_ctx(lithology=ClassifiedUnit("alluvium", None, "s1"),
                   cell=make_cell(lineament_density=None))
    r = run(cfg, ctx, today)
    lin = next(f for f in r.factors if f.key == "lineament_density")
    assert not lin.applicable
    assert "lineament_density" not in r.missing                  # N/A is not "missing data"
    assert r.coverage == pytest.approx(1.0)


def test_unknown_class_treated_as_missing(cfg, today):
    from app.engine.types import ClassifiedUnit
    r = run(cfg, make_ctx(soil=ClassifiedUnit("moon_dust", None, "s1")), today)
    assert "soil" in r.missing


def test_thresholds_classification(cfg):
    assert cfg.classify(80) == "high" and cfg.classify(cfg.classes["moderate"]["min_score"]) == "moderate"
    assert cfg.classify(0) == "very_low" and cfg.classify(None) == "insufficient_data"
