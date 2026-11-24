"""Per-state configuration loader and validator."""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(os.environ.get("STATE_CONFIG_DIR", Path(__file__).resolve().parents[2] / "config" / "states"))
CLASS_ORDER = ["high", "moderate", "low", "very_low"]      # best -> worst
INSUFFICIENT = "insufficient_data"


class ConfigError(ValueError):
    pass


class StateConfig:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self._validate()

    # ---- convenient accessors ----------------------------------------------
    @property
    def code(self) -> str:
        return self.raw["state"]["code"]

    @property
    def name(self) -> dict:
        return self.raw["state"]["name"]

    @property
    def map_bounds(self):
        return self.raw["state"]["map_bounds"]

    @property
    def method_version(self) -> str:
        return self.raw["method"]["version"]

    @property
    def method_name(self) -> dict:
        return self.raw["method"]["name"]

    @property
    def classes(self) -> dict:
        return self.raw["classes"]

    @property
    def factors(self) -> dict:
        return self.raw["factors"]

    def section(self, name: str) -> dict:
        return self.raw[name]

    @property
    def hard_rock_lithologies(self) -> set[str]:
        return set(self.raw.get("settings", {}).get("hard_rock_lithologies", []))

    # ---- classification -------------------------------------------------------
    def classify(self, score: float | None) -> str:
        if score is None:
            return INSUFFICIENT
        for key in CLASS_ORDER:
            if score >= self.classes[key]["min_score"]:
                return key
        return CLASS_ORDER[-1]

    def class_label(self, key: str) -> dict:
        return self.classes[key]["label"]

    def class_color(self, key: str) -> str:
        return self.classes[key]["color"]

    def class_rank(self, key: str) -> int:
        """0 = worst ... 3 = best; insufficient data => -1."""
        if key == INSUFFICIENT:
            return -1
        return len(CLASS_ORDER) - 1 - CLASS_ORDER.index(key)

    def categorical_label(self, factor_key: str, class_key: str) -> dict | None:
        item = self.factors[factor_key].get("classes", {}).get(class_key)
        return item["label"] if item else None

    # ---- validation -----------------------------------------------------------
    def _validate(self) -> None:
        r = self.raw
        for key in ("state", "method", "classes", "regional", "factors", "water_table",
                    "evidence", "depth", "confidence", "ml"):
            if key not in r:
                raise ConfigError(f"missing section '{key}'")
        total = sum(f["weight"] for f in r["factors"].values())
        if abs(total - 1.0) > 1e-6:
            raise ConfigError(f"factor weights must sum to 1.0, got {total:.4f}")
        for fk, f in r["factors"].items():
            if f["kind"] == "numeric":
                xs = [p[0] for p in f["points"]]
                if xs != sorted(xs) or len(set(xs)) != len(xs):
                    raise ConfigError(f"factor {fk}: points must have strictly increasing x")
                if any(not 0 <= p[1] <= 100 for p in f["points"]):
                    raise ConfigError(f"factor {fk}: scores must be within 0..100")
            elif f["kind"] == "categorical":
                if any(not 0 <= c["score"] <= 100 for c in f["classes"].values()):
                    raise ConfigError(f"factor {fk}: class scores must be within 0..100")
            else:
                raise ConfigError(f"factor {fk}: unknown kind {f['kind']}")
        mins = [r["classes"][k]["min_score"] for k in CLASS_ORDER]
        if mins != sorted(mins, reverse=True):
            raise ConfigError("class min_score thresholds must be descending")
        if abs(sum(r["confidence"]["weights"].values()) - 1.0) > 1e-6:
            raise ConfigError("confidence weights must sum to 1.0")
        for req in r["regional"]["required_factors"]:
            if req not in r["factors"]:
                raise ConfigError(f"required factor {req} is not defined")


@functools.lru_cache(maxsize=8)
def load_state_config(code_or_path: str = "telangana") -> StateConfig:
    p = Path(code_or_path)
    if not p.suffix:
        p = CONFIG_DIR / f"{code_or_path}.yaml"
    with open(p, "r", encoding="utf-8") as fh:
        return StateConfig(yaml.safe_load(fh))
