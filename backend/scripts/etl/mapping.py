"""Pure helpers for loading real datasets: class mapping, validation, season, outcome. No DB, no network."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

OUTCOMES = ("dry", "low", "moderate", "good")


def map_alias(raw: Optional[str], aliases: dict[str, str]) -> Optional[str]:
    """Case-insensitive 'contains' match; the LONGEST matching key wins (so 'clay loam' beats 'loam')."""
    if raw is None:
        return None
    text = str(raw).casefold()
    best: Optional[str] = None
    best_len = -1
    for key, cls in aliases.items():
        k = key.casefold()
        if k in text and len(k) > best_len:
            best, best_len = cls, len(k)
    return best


def season_for(d: date) -> str:
    """CGWB measures in Jan, May (pre-monsoon), Aug and Nov (post-monsoon)."""
    m = d.month
    if m in (4, 5, 6):
        return "pre_monsoon"
    if m in (7, 8, 9):
        return "monsoon"
    if m in (10, 11, 12):
        return "post_monsoon"
    return "winter"


def parse_thresholds(spec: str) -> list[tuple[str, float]]:
    """'low<60,moderate<180' -> [('low', 60.0), ('moderate', 180.0)]; yields >= the last bound are 'good'; 0 is 'dry'."""
    out = []
    for part in spec.split(","):
        name, _, val = part.strip().partition("<")
        if name.strip() not in ("low", "moderate") or not val:
            raise ValueError("thresholds look like 'low<60,moderate<180' (litres per minute)")
        out.append((name.strip(), float(val)))
    if [n for n, _ in out] != ["low", "moderate"] or out[0][1] >= out[1][1]:
        raise ValueError("give both 'low<X' and 'moderate<Y' with X < Y")
    return out


def outcome_from_yield(yield_lpm: float, thresholds: list[tuple[str, float]]) -> str:
    """Only with thresholds the operator supplies explicitly - this project does not assume any."""
    if yield_lpm <= 0:
        return "dry"
    for name, bound in thresholds:
        if yield_lpm < bound:
            return name
    return "good"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok: int = 0

    def err(self, row: int, msg: str) -> None:
        self.errors.append(f"row {row}: {msg}")

    def summary(self) -> str:
        s = f"{self.ok} valid, {len(self.errors)} rejected, {len(self.warnings)} warnings"
        if self.errors:
            s += "\n  " + "\n  ".join(self.errors[:15]) + (f"\n  ... {len(self.errors) - 15} more" if len(self.errors) > 15 else "")
        return s


def _num(v, name: str) -> float:
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{name} is not a number: {v!r}")
    if not math.isfinite(x):
        raise ValueError(f"{name} is not finite")
    return x


def opt_num(v, name: str) -> Optional[float]:
    return None if v is None or str(v).strip() == "" else _num(v, name)


def req_num(v, name: str) -> float:
    return _num(v, name)


def check_latlon(lat: float, lon: float, bounds) -> None:
    """bounds = [[lat_min, lon_min], [lat_max, lon_max]] (the state's map_bounds)."""
    (la0, lo0), (la1, lo1) = bounds
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat/lon out of range (are they swapped?)")
    if not (la0 <= lat <= la1 and lo0 <= lon <= lo1):
        raise ValueError(f"({lat}, {lon}) is outside the state's bounds - wrong state, or lat/lon swapped?")


def parse_date(v: str) -> date:
    v = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date {v!r} (use YYYY-MM-DD)")


def read_csv(path: str | Path, required: Iterable[str]) -> list[tuple[int, dict]]:
    """Rows as (row_number, dict) with lower-cased, stripped header names. Fails early on missing columns."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        cols = [c.strip().lower() for c in (rd.fieldnames or [])]
        missing = [c for c in required if c not in cols]
        if missing:
            raise ValueError(f"{path}: missing column(s) {missing}; found {cols}")
        return [(i, {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}) for i, row in enumerate(rd, start=2)]
