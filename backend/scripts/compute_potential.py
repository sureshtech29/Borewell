"""Pre-compute the regional groundwater-potential class of every grid cell (the coloured map layer).

    python -m scripts.compute_potential [--batch 2000] [--dry-run]

Run after loading data (and again whenever water-level data or the state config changes).
Uses exactly the same code path as the per-location analysis (engine.scoring.regional_for_point),
so the colour on the map and the class in the report can never disagree.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date

from app.engine import load_state_config
from app.engine.scoring import regional_for_point
from app.engine.wells import prepare_wells
from app.repository.postgis import PostgisRepository
from app.settings import load_settings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--dry-run", action="store_true", help="compute and report the class counts without writing")
    args = ap.parse_args(argv)

    st = load_settings()
    if st.backend != "postgis":
        print("compute_potential needs DATABASE_URL (PostGIS backend)", file=sys.stderr)
        return 2
    cfg = load_state_config(st.state)
    repo = PostgisRepository(st.database_url, cfg, st.data_mode)
    try:
        today = date.today()
        pw = prepare_wells(repo.load_all_wells(today), cfg, today)
        print(f"mode={st.data_mode} state={cfg.code} wells with usable readings: {len(pw.lat)}")
        counts: Counter = Counter()
        total = 0
        for batch in repo.iter_regional_inputs(args.batch):
            out = []
            for lat, lon, cell, lith, aq, soil in batch:
                r = regional_for_point(lat=lat, lon=lon, cell=cell, lithology=lith, aquifer=aq, soil=soil,
                                       prepared_wells=pw, cfg=cfg)
                counts[r.klass] += 1
                out.append({"cell_id": cell.cell_id, "score": r.score, "klass": r.klass, "coverage": round(r.coverage, 3),
                            "factors": json.dumps({f.key: (None if f.score is None else round(f.score, 1)) for f in r.factors}),
                            "version": cfg.method_version})
            total += len(out)
            if not args.dry_run:
                repo.write_potential(out)
            print(f"  {total} cells", end="\r", flush=True)
        print(f"\n{total} cells {'computed (not written)' if args.dry_run else 'written'}: "
              + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        if total and counts.get("insufficient_data", 0) / total > 0.5:
            print("WARNING: more than half of the cells have insufficient data - check the geology layer and the grid.")
        return 0
    finally:
        repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
