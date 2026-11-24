"""Regenerate backend/db/seed_demo.sql from the synthetic demo dataset.

    cd backend && python -m scripts.make_demo_sql [--out db/seed_demo.sql] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from app.engine.config import load_state_config
from demo.export_sql import export_seed_sql
from demo.generate import build_demo_dataset


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "db" / "seed_demo.sql"))
    ap.add_argument("--today", default=None, help="reference date for water-level windows (default: today)")
    args = ap.parse_args()
    cfg = load_state_config("telangana")
    ds = build_demo_dataset(cfg=cfg)
    today = date.fromisoformat(args.today) if args.today else date.today()
    sql = export_seed_sql(ds, cfg, today)
    Path(args.out).write_text(sql, encoding="utf-8")
    print(f"wrote {args.out} ({len(sql) / 1e6:.1f} MB) - SYNTHETIC DEMO DATA")


if __name__ == "__main__":
    main()
