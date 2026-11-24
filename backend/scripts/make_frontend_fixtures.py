"""Regenerate the API fixtures used by the frontend render tests (frontend/test/fixtures/).

    python -m scripts.make_frontend_fixtures

Runs the engine on the SYNTHETIC demo data (in-memory backend) and writes /meta plus one /analyze response for every
combination of potential class and depth-range availability that the demo area contains, plus one point outside the
covered area. Re-run it when the demo data, the engine output shape or the state config changes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_DATA_MODE", "demo")
os.environ.pop("DATABASE_URL", None)

from app.services import build_container, build_meta, run_analysis  # noqa: E402
from app.settings import load_settings  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "test" / "fixtures"


def main() -> int:
    c = build_container(load_settings())
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("analysis_*.json"):
        old.unlink()
    found: dict[tuple[str, bool], dict] = {}
    (s, w), (n, e) = c.cfg.map_bounds
    steps = 40
    for i in range(steps + 1):
        for j in range(steps + 1):
            a = run_analysis(c, s + (n - s) * i / steps, w + (e - w) * j / steps, 25.0)
            if a["status"] == "ok":
                found.setdefault((a["potential"]["class"], bool(a["drilling_depth"]["available"])), a)
    for (klass, has_depth), a in sorted(found.items()):
        name = f"analysis_{klass}_{'depth' if has_depth else 'nodepth'}.json"
        (OUT / name).write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
        print("wrote", name)
    outside = run_analysis(c, 12.90, 77.60, None)          # Bengaluru: outside the demo area
    assert outside["status"] != "ok"
    (OUT / "analysis_outside.json").write_text(json.dumps(outside, ensure_ascii=False), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(build_meta(c), ensure_ascii=False), encoding="utf-8")
    print("wrote analysis_outside.json, meta.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
