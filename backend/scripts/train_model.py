"""Train the optional statistical (gradient-boosting) second opinion from REAL borewell records.

    python -m scripts.train_model [--out DIR]

Writes model.joblib + metrics.json to ML_MODEL_DIR (default backend/models/<mode>). The API serves the model
only if it passes the gate in the state config (ml.min_records, ml.min_cv_auc, spatial-block cross-validation)
AND it was trained on the same data mode the API runs in. A failed gate is not an error: the API simply reports
"statistical model not available". Metrics are printed either way so the result can be judged honestly.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.engine import load_state_config
from app.engine.ml import train_model
from app.engine.training import build_training_rows
from app.repository.postgis import PostgisRepository
from app.settings import load_settings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    st = load_settings()
    if st.backend != "postgis":
        print("train_model needs DATABASE_URL (PostGIS backend)", file=sys.stderr)
        return 2
    cfg = load_state_config(st.state)
    repo = PostgisRepository(st.database_url, cfg, st.data_mode)
    try:
        rows, stats = build_training_rows(repo, cfg, date.today())
    finally:
        repo.close()
    print("training table:", stats)
    gate = cfg.section("ml")
    if len(rows) < 50:
        print(f"only {len(rows)} usable records - not enough to even evaluate a model (the serving gate is {gate['min_records']}).")
        return 1
    meta = train_model(rows, cfg, st.data_mode, args.out or st.ml_model_dir)
    print(f"records={meta['n_train']}  productive share={meta['positive_rate']:.2f}  cross-validated AUC={meta['cv_auc']}  ({meta['cv']})")
    if meta["passes_gate"]:
        print("gate PASSED: the API will show the model as a second opinion next to the weighted-overlay index.")
    else:
        print(f"gate NOT passed (need >= {gate['min_records']} records and AUC >= {gate['min_cv_auc']}): "
              "the API will report that no statistical model is available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
