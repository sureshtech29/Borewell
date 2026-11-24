"""Environment-driven settings (no third-party settings library needed)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_mode: str                    # demo | production
    backend: str                      # memory | postgis
    database_url: Optional[str]
    state: str                        # config/states/<state>.yaml
    cors_origins: list[str]
    show_record_points: bool
    contact_email: Optional[str]
    ml_model_dir: Path
    min_zoom_potential: int
    max_cells: int
    rate_limit_per_min: int
    ai_provider: str
    ai_base_url: str
    ai_model: str
    ai_api_key: Optional[str]


def load_settings() -> Settings:
    mode = os.environ.get("APP_DATA_MODE", "demo").strip().lower()
    if mode not in ("demo", "production"):
        raise ValueError("APP_DATA_MODE must be 'demo' or 'production'")
    db = os.environ.get("DATABASE_URL") or None
    backend = os.environ.get("APP_DATA_BACKEND", "postgis" if db else "memory").strip().lower()
    if backend not in ("memory", "postgis"):
        raise ValueError("APP_DATA_BACKEND must be 'memory' or 'postgis'")
    if backend == "postgis" and not db:
        raise ValueError("APP_DATA_BACKEND=postgis requires DATABASE_URL")
    if backend == "memory" and mode == "production":
        raise ValueError("The in-memory backend only holds synthetic demo data; "
                         "use APP_DATA_BACKEND=postgis with APP_DATA_MODE=production")
    cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o.strip()]
    return Settings(
        data_mode=mode, backend=backend, database_url=db,
        state=os.environ.get("APP_STATE", "telangana"), cors_origins=cors,
        # Individual borewell points are sensitive in production; visible by default only for demo data.
        show_record_points=_bool("SHOW_RECORD_POINTS", mode == "demo"),
        contact_email=os.environ.get("CONTACT_EMAIL") or None,
        ml_model_dir=Path(os.environ.get("ML_MODEL_DIR", BACKEND_DIR / "models" / mode)),
        min_zoom_potential=_int("MIN_ZOOM_POTENTIAL", 8),
        max_cells=_int("MAX_CELLS_PER_REQUEST", 8000),
        rate_limit_per_min=_int("RATE_LIMIT_PER_MIN", 60),
        ai_provider=os.environ.get("AI_PROVIDER", "openai-compatible"),
        ai_base_url=os.environ.get("AI_BASE_URL", "https://api.openai.com/v1"),
        ai_model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
        ai_api_key=os.environ.get("AI_API_KEY") or None,
    )
