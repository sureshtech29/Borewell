"""Optional statistical model (gradient boosting) trained on real borewell outcomes.

It is a SECOND OPINION shown next to the weighted-overlay index; it never replaces it.
A model is used by the API only if it passes a gate:
    * enough training records            (ml.min_records)
    * spatial-block CV AUC high enough   (ml.min_cv_auc)
    * trained on the same data mode the API runs in (a model trained on the synthetic
      demo data is never served in production mode, and vice versa)
Otherwise the API reports "statistical model not available" - nothing is faked.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from .config import StateConfig
from .scoring import FactorResult

AGREE_HI = 0.65
AGREE_LO = 0.35


def feature_keys(cfg: StateConfig) -> list[str]:
    return list(cfg.factors.keys())


def feature_vector(factors: Sequence[FactorResult], cfg: StateConfig) -> list[float]:
    by = {f.key: f for f in factors}
    out = []
    for k in feature_keys(cfg):
        f = by.get(k)
        out.append(float(f.score) if (f is not None and f.available and f.score is not None) else math.nan)
    return out


@dataclass
class MlResult:
    probability: float
    cv_auc: float
    n_train: int
    trained_on_demo: bool
    agrees: Optional[bool]


class MlModel:
    def __init__(self, estimator, meta: dict):
        self.estimator = estimator
        self.meta = meta

    def predict(self, vec: list[float], class_rank: int) -> MlResult:
        p = float(self.estimator.predict_proba(np.array([vec], dtype=float))[0, 1])
        agrees: Optional[bool] = None
        if class_rank >= 2 and p < AGREE_LO:      # index says moderate/high, model says unlikely
            agrees = False
        elif class_rank in (0, 1) and p >= AGREE_HI:
            agrees = False
        else:
            agrees = True
        return MlResult(round(p, 3), float(self.meta["cv_auc"]), int(self.meta["n_train"]),
                        bool(self.meta["trained_on_demo"]), agrees)


def load_model(model_dir: str | Path, cfg: StateConfig, data_mode: str) -> Optional[MlModel]:
    """Return the model only if it passes the gate, else None (and the API says so)."""
    model_dir = Path(model_dir)
    meta_p, model_p = model_dir / "metrics.json", model_dir / "model.joblib"
    if not (meta_p.exists() and model_p.exists()):
        return None
    meta = json.loads(meta_p.read_text())
    gate = cfg.section("ml")
    if meta.get("n_train", 0) < gate["min_records"] or meta.get("cv_auc", 0) < gate["min_cv_auc"]:
        return None
    if bool(meta.get("trained_on_demo")) != (data_mode == "demo"):
        return None
    if meta.get("method_version") != cfg.method_version or meta.get("features") != feature_keys(cfg):
        return None
    import joblib  # lazy: keeps API start-up light when no model is deployed
    return MlModel(joblib.load(model_p), meta)


def train_model(rows: list[tuple[list[float], int, tuple[int, int]]], cfg: StateConfig, data_mode: str,
                out_dir: str | Path) -> dict:
    """rows = [(feature_vector, label 0/1, spatial_block_id)]. Returns the metrics dict.

    Always writes metrics.json (so a failed gate is visible); writes model.joblib too.
    The gate itself is applied at load time.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold, cross_val_predict
    import joblib

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    X = np.array([r[0] for r in rows], dtype=float)
    y = np.array([r[1] for r in rows], dtype=int)
    block_ids: dict = {}
    groups = np.array([block_ids.setdefault(r[2], len(block_ids)) for r in rows])
    if len(set(y)) < 2:
        raise ValueError("training data has a single class; cannot fit a model")

    est = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                         l2_regularization=1.0, random_state=0)
    n_splits = max(2, min(5, len(set(groups))))
    proba = cross_val_predict(est, X, y, groups=groups, cv=GroupKFold(n_splits=n_splits),
                              method="predict_proba")[:, 1]
    auc = float(roc_auc_score(y, proba))
    est.fit(X, y)

    meta = {
        "method_version": cfg.method_version,
        "features": feature_keys(cfg),
        "n_train": int(len(rows)),
        "positive_rate": float(y.mean()),
        "cv": f"spatial-block GroupKFold({n_splits}), block={cfg.section('ml')['block_size_km']} km",
        "cv_auc": round(auc, 4),
        "trained_on_demo": data_mode == "demo",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gate": cfg.section("ml"),
        "passes_gate": bool(len(rows) >= cfg.section("ml")["min_records"] and auc >= cfg.section("ml")["min_cv_auc"]),
    }
    joblib.dump(est, out / "model.joblib")
    (out / "metrics.json").write_text(json.dumps(meta, indent=2))
    return meta
