from datetime import date

import pytest

from app.engine.confidence import compute_confidence
from app.engine.depth import drilling_depth_range
from app.engine.evidence import blend, compute_local_evidence
from app.engine.wells import summarize_wells
from tests.conftest import make_bw, make_ctx, make_ves, make_well


# ------------------------------------------------------------------ local evidence
def test_no_records_means_regional_unchanged(cfg):
    ev = compute_local_evidence(make_ctx(), cfg)
    assert not ev.used and blend(55.0, ev, cfg) == 55.0


def test_dry_neighbours_pull_score_down_and_more_records_pull_harder(cfg):
    few = compute_local_evidence(make_ctx(borewells=[make_bw(i, outcome="dry") for i in range(2)]), cfg)
    many = compute_local_evidence(make_ctx(borewells=[make_bw(i, outcome="dry") for i in range(10)]), cfg)
    b_few, b_many = blend(60.0, few, cfg), blend(60.0, many, cfg)
    assert b_many < b_few < 60.0


def test_distant_records_count_less(cfg):
    near = compute_local_evidence(make_ctx(borewells=[make_bw(1, outcome="good")]), cfg)
    far = compute_local_evidence(make_ctx(borewells=[make_bw(1, lat=17.52, outcome="good")]), cfg)   # ~2.2 km
    assert near.effective_n > far.effective_n > 0


def test_records_beyond_radius_ignored_but_counted_in_search(cfg):
    ev = compute_local_evidence(make_ctx(borewells=[make_bw(1, lat=17.58, outcome="good")]), cfg)   # ~9 km
    assert ev.n_borewells_radius == 0 and ev.n_borewells_search == 1 and not ev.used


def test_poor_location_accuracy_halves_weight(cfg):
    good = compute_local_evidence(make_ctx(borewells=[make_bw(1, acc=20)]), cfg)
    poor = compute_local_evidence(make_ctx(borewells=[make_bw(1, acc=2000)]), cfg)
    assert poor.borewell_weight == pytest.approx(good.borewell_weight / 2)


def test_ves_adds_weight(cfg):
    ev = compute_local_evidence(make_ctx(ves=[make_ves(1, "poor")]), cfg)
    assert ev.used and ev.ves_near and ev.mean_score == cfg.section("evidence")["ves_scores"]["poor"]


# ------------------------------------------------------------------ depth range
def test_depth_unavailable_below_minimum_records(cfg):
    d = drilling_depth_range(make_ctx(borewells=[make_bw(i, depth=300 + i * 10) for i in range(4)]), cfg)
    assert not d.available and d.reason == "insufficient_records" and d.low_ft is None and d.high_ft is None


def test_depth_available_with_enough_productive_records(cfg):
    bws = [make_bw(i, depth=250 + i * 10, outcome="good") for i in range(8)]
    d = drilling_depth_range(make_ctx(borewells=bws), cfg)
    assert d.available and d.n_productive == 8 and d.radius_km == 5.0
    assert 250 <= d.low_ft <= d.high_ft <= 320 and d.low_ft % 10 == 0


def test_dry_wells_do_not_count_toward_depth_range(cfg):
    bws = [make_bw(i, outcome="dry", depth=600) for i in range(20)] + [make_bw(99, outcome="good")]
    d = drilling_depth_range(make_ctx(borewells=bws), cfg)
    assert not d.available


def test_depth_falls_back_to_wider_radius(cfg):
    bws = [make_bw(i, lat=17.55, depth=300, outcome="moderate") for i in range(6)]       # ~5.5 km away
    d = drilling_depth_range(make_ctx(borewells=bws), cfg)
    assert d.available and d.radius_km == 10.0


def test_no_records_reason(cfg):
    d = drilling_depth_range(make_ctx(), cfg)
    assert not d.available and d.reason == "no_records"


# ------------------------------------------------------------------ water table
def test_water_table_needs_two_wells(cfg, today):
    one = summarize_wells(17.5, 78.0, [make_well(1, 17.52, 78.0)], cfg, today)
    assert not one.available and one.reason == "too_few_wells"
    two = summarize_wells(17.5, 78.0, [make_well(1, 17.52, 78.0, pre=8), make_well(2, 17.5, 78.03, pre=12)], cfg, today)
    assert two.available and two.pre_range_m == (8, 12) and 8 <= two.pre_idw_m <= 12


def test_water_table_ignores_far_wells(cfg, today):
    w = summarize_wells(17.5, 78.0, [make_well(1, 18.5, 78.0), make_well(2, 18.6, 78.0)], cfg, today)
    assert not w.available and w.reason == "no_wells_in_radius"


def test_old_readings_outside_window_are_ignored(cfg, today):
    old = [make_well(1, 17.52, 78.0, years=(2015, 2016)), make_well(2, 17.5, 78.03, years=(2015, 2016))]
    w = summarize_wells(17.5, 78.0, old, cfg, today)
    assert not w.available and w.reason == "no_recent_readings"


def test_declining_trend_detected(cfg, today):
    from app.engine.types import ObservationWell, Reading
    rd = [Reading(date(y, 5, 15), "pre_monsoon", 5 + 1.0 * (y - 2018)) for y in range(2018, 2027)]
    wells = [ObservationWell(i, f"W{i}", 17.5 + i * 0.01, 78.0, list(rd), source_id="s1") for i in (1, 2)]
    w = summarize_wells(17.5, 78.0, wells, cfg, today)
    assert w.trend_m_per_yr == pytest.approx(1.0, abs=0.05)


# ------------------------------------------------------------------ confidence
def test_confidence_high_is_capped_without_local_records(cfg, today):
    ctx = make_ctx(ves=[make_ves(1)], borewells=[make_bw(i, outcome="moderate") for i in range(3)])
    ev = compute_local_evidence(ctx, cfg)
    wt = summarize_wells(ctx.lat, ctx.lon, ctx.wells, cfg, today)
    c = compute_confidence(coverage=1.0, regional_score=60, final_score=60, evidence=ev, water=wt, cfg=cfg, today=today)
    assert c.score <= 1.0 and c.level in ("low", "medium", "high")
    assert abs(sum(x.weight for x in c.components) - 1.0) < 1e-9


def test_confidence_low_when_nothing_but_terrain(cfg, today):
    ctx = make_ctx(wells=[])
    ev = compute_local_evidence(ctx, cfg)
    wt = summarize_wells(ctx.lat, ctx.lon, ctx.wells, cfg, today)
    c = compute_confidence(coverage=0.85, regional_score=60, final_score=60, evidence=ev, water=wt, cfg=cfg, today=today)
    assert c.level == "low"


def test_confidence_cap_rule(cfg, today):
    """Strong coverage + 3 close wells + recent data would score 'high', but with only 2 local records
    (effective_n < high_requires_effective_n) the level must be capped to 'medium'."""
    ctx = make_ctx(borewells=[make_bw(i, outcome="moderate") for i in (1, 2)],
                   wells=[make_well(i, 17.5 + i * 0.005, 78.0) for i in (1, 2, 3)])
    ev = compute_local_evidence(ctx, cfg)
    assert ev.effective_n < cfg.section("confidence")["high_requires_effective_n"]
    wt = summarize_wells(ctx.lat, ctx.lon, ctx.wells, cfg, today)
    c = compute_confidence(coverage=1.0, regional_score=55, final_score=57, evidence=ev, water=wt, cfg=cfg, today=today)
    assert c.score >= cfg.section("confidence")["levels"]["high_from"]
    assert c.capped and c.level == "medium"


def test_confidence_can_reach_high_with_rich_local_evidence(cfg, today):
    ctx = make_ctx(borewells=[make_bw(i, outcome="moderate") for i in range(1, 7)], ves=[make_ves(1, "moderate")],
                   wells=[make_well(i, 17.5 + i * 0.005, 78.0) for i in (1, 2, 3)])
    ev = compute_local_evidence(ctx, cfg)
    wt = summarize_wells(ctx.lat, ctx.lon, ctx.wells, cfg, today)
    c = compute_confidence(coverage=1.0, regional_score=60, final_score=61, evidence=ev, water=wt, cfg=cfg, today=today)
    assert c.level == "high" and not c.capped
