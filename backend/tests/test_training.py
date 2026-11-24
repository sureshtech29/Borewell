from __future__ import annotations

import json
from datetime import date

import pytest

pytest.importorskip("sklearn")

from app.engine import analyze
from app.engine.ml import load_model
from app.engine.training import block_id, build_training_rows
from app.engine.ml import train_model
from app.present import present
from app.schemas import AnalysisResponse


def test_block_id_is_stable_and_blocks_are_about_block_km():
    a = block_id(17.45, 78.35, 5.0)
    assert a == block_id(17.45, 78.35, 5.0)
    assert block_id(17.45, 78.35 + 0.01, 5.0) in (a, (a[0], a[1] + 1))       # 1 km away: same or adjacent block
    assert block_id(17.45, 78.35 + 0.2, 5.0) != a                              # ~21 km away: different block


@pytest.fixture(scope="module")
def trained(demo_repo, cfg, tmp_path_factory):
    rows, stats = build_training_rows(demo_repo, cfg, date(2026, 11, 21))
    out = tmp_path_factory.mktemp("model")
    meta = train_model(rows, cfg, "demo", out)
    return rows, stats, meta, out


def test_training_rows_cover_demo_borewells(trained):
    rows, stats, _, _ = trained
    assert stats["records"] >= 500 and stats["used"] == len(rows) > 400
    assert {r[1] for r in rows} == {0, 1}
    assert all(len(r[0]) == 9 for r in rows)


def test_metrics_are_recorded_and_flag_demo(trained):
    _, _, meta, out = trained
    assert meta["trained_on_demo"] is True and 0.5 < meta["cv_auc"] <= 1.0
    assert json.loads((out / "metrics.json").read_text())["cv"].startswith("spatial-block GroupKFold")


def test_demo_model_is_never_served_in_production_mode(trained, cfg):
    _, _, _, out = trained
    assert load_model(out, cfg, "production") is None            # trained on synthetic data


def test_gate_decides_whether_the_model_loads(trained, cfg):
    _, _, meta, out = trained
    m = load_model(out, cfg, "demo")
    assert (m is not None) == bool(meta["passes_gate"])


class _Stub:
    """Stands in for a fitted estimator so the 'model available' code path is tested without a real model."""
    def __init__(self, p):
        self.p = p

    def predict_proba(self, X):
        import numpy as np
        return np.array([[1 - self.p, self.p] for _ in X])


@pytest.mark.parametrize("p,agrees_expected", [(0.9, True), (0.1, False)])
def test_model_adds_second_opinion_but_not_a_different_class(cfg, demo_repo, p, agrees_expected):
    from app.engine.ml import MlModel
    from app.engine.types import Radii
    ctx = demo_repo.point_context(17.45, 78.35, Radii())
    without = analyze(ctx, cfg, today=date(2026, 11, 21))
    if cfg.class_rank(without.klass) < 2:
        pytest.skip("test point is not moderate/high in this demo build")
    model = MlModel(_Stub(p), {"cv_auc": 0.74, "n_train": 800, "trained_on_demo": True})
    with_ml = analyze(ctx, cfg, today=date(2026, 11, 21), ml_model=model)
    assert with_ml.klass == without.klass and with_ml.score == without.score      # second opinion only
    j = present(with_ml, cfg)
    AnalysisResponse.model_validate(j)
    assert j["statistical_model"]["status"] == "available"
    assert j["statistical_model"]["trained_on_demo"] is True
    assert with_ml.ml.agrees is agrees_expected


def test_without_a_model_the_api_says_so(cfg, demo_repo):
    from app.engine.types import Radii
    ctx = demo_repo.point_context(17.45, 78.35, Radii())
    j = present(analyze(ctx, cfg, today=date(2026, 11, 21)), cfg)
    assert j["statistical_model"]["status"] != "available"
