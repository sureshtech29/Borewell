"""Wiring: build the repository/config/model container and run one analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import __version__, i18n
from .engine import analyze, load_state_config
from .engine.config import CLASS_ORDER, INSUFFICIENT
from .engine.config import StateConfig
from .engine.ml import MlModel, load_model
from .engine.types import Radii
from .present import present
from .repository.base import Repository
from .settings import Settings


@dataclass
class Container:
    settings: Settings
    cfg: StateConfig
    repo: Repository
    ml_model: Optional[MlModel]

    def radii(self) -> Radii:
        wt, ev = self.cfg.section("water_table"), self.cfg.section("evidence")
        return Radii(wells_km=float(wt["max_radius_km"]), borewells_km=float(ev["borewell_search_max_km"]),
                     ves_km=float(ev["ves_radius_km"]), rainfall_years=15)


def build_container(settings: Settings) -> Container:
    cfg = load_state_config(settings.state)
    if settings.backend == "memory":
        from demo.generate import build_demo_dataset
        from .repository.memory import MemoryRepository
        repo: Repository = MemoryRepository(build_demo_dataset(cfg=cfg), cfg)
    else:
        from .repository.postgis import PostgisRepository
        repo = PostgisRepository(settings.database_url, cfg, settings.data_mode)
    return Container(settings, cfg, repo, load_model(settings.ml_model_dir, cfg, settings.data_mode))


def run_analysis(c: Container, lat: float, lon: float, accuracy_m: Optional[float] = None) -> dict:
    ctx = c.repo.point_context(lat, lon, c.radii())
    res = analyze(ctx, c.cfg, accuracy_m=accuracy_m, ml_model=c.ml_model)
    return present(res, c.cfg, accuracy_m=accuracy_m)


def build_meta(c: Container) -> dict:
    """Everything the web app needs at start-up (kept free of FastAPI so it is unit-testable)."""
    cfg = c.cfg
    legend = [{"key": k, "color": cfg.class_color(k), "label": cfg.class_label(k),
               "min_score": cfg.classes[k]["min_score"]} for k in CLASS_ORDER + [INSUFFICIENT]]
    return {
        "app": "Borewell Water Finder", "version": __version__, "data_mode": c.repo.data_mode,
        "state": c.repo.state_info(), "languages": ["en", "te"], "legend": legend,
        "layers": c.repo.layer_counts(), "min_zoom_for_potential_layer": c.settings.min_zoom_potential,
        "show_record_points": c.settings.show_record_points, "contact_email": c.settings.contact_email,
        "ml_available": c.ml_model is not None,
        "method": {"version": cfg.method_version, "name": cfg.method_name,
                   "factors": [{"key": k, "label": f["label"], "weight": f["weight"]} for k, f in cfg.factors.items()]},
        "disclaimer": i18n.MESSAGES["disclaimer"],
    }


def build_datasets(c: Container) -> dict:
    return {"data_mode": c.repo.data_mode, "sources": c.repo.datasets(), "layer_counts": c.repo.layer_counts()}
