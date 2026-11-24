import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import load_state_config  # noqa: E402
from app.engine.types import (BorewellRecord, ClassifiedUnit, FeatureCell, ObservationWell, PointContext,  # noqa: E402
                              Reading, SourceRef, VesSurvey)

TODAY = date(2026, 11, 21)


@pytest.fixture(scope="session")
def cfg():
    return load_state_config("telangana")


@pytest.fixture(scope="session")
def today():
    return TODAY


_DEMO_REPO = {}


def _demo_repo_singleton(cfg):
    """One shared in-memory demo repository per test session (building it takes a few seconds)."""
    if "r" not in _DEMO_REPO:
        from demo.generate import build_demo_dataset
        from app.repository.memory import MemoryRepository
        _DEMO_REPO["r"] = MemoryRepository(build_demo_dataset(), cfg)
    return _DEMO_REPO["r"]


@pytest.fixture(scope="session")
def demo_repo(cfg):
    return _demo_repo_singleton(cfg)


def src(sid="s1", kind="geology", updated=date(2026, 1, 1), demo=False):
    return SourceRef(source_id=sid, name_en=sid, publisher="test", layer_kind=kind,
                     data_last_updated=updated, is_demo=demo)


def make_cell(**kw):
    base = dict(cell_id=1, elevation_m=500, slope_deg=2.0, tpi_m=0.0, drainage_density=1.5,
                lineament_density=1.0, rainfall_normal_mm=800, rainfall_cv=25,
                source_ids={"slope": "s1", "drainage_density": "s1", "lineament_density": "s1",
                            "rainfall": "s1", "topographic_position": "s1"})
    base.update(kw)
    return FeatureCell(**base)


def make_well(i, lat, lon, pre=10.0, post=5.0, years=(2024, 2025, 2026)):
    rd = []
    for y in years:
        rd.append(Reading(date(y, 5, 15), "pre_monsoon", pre))
        if y < 2026:
            rd.append(Reading(date(y, 11, 15), "post_monsoon", post))
    return ObservationWell(i, f"W{i}", lat, lon, rd, source_id="s1")


def make_ctx(**kw):
    """A fully-populated granite/gneiss context at (17.5, 78.0) with no local evidence."""
    base = dict(lat=17.5, lon=78.0, in_coverage=True, data_mode="production",
                cell=make_cell(),
                lithology=ClassifiedUnit("granite_gneiss", "gneiss", "s1"),
                aquifer=ClassifiedUnit("weathered_fractured_crystalline", None, "s1"),
                soil=ClassifiedUnit("red_soil", None, "s1"),
                wells=[make_well(1, 17.52, 78.0), make_well(2, 17.5, 78.05)],
                sources={"s1": src("s1")})
    base.update(kw)
    return PointContext(**base)


def make_bw(i, lat=17.5, lon=78.0, outcome="moderate", depth=300.0, acc=None, year=2020):
    return BorewellRecord(i, lat, lon, depth, outcome, yield_lpm=50.0, drilled_year=year,
                          location_accuracy_m=acc, source_id="s1")


def make_ves(i, suit="good", lat=17.5, lon=78.0):
    return VesSurvey(i, lat, lon, "VES", suit, 2020, 10.0, 30.0, 50.0, None, "s1")


@pytest.fixture(scope="session")
def container(cfg, demo_repo):
    """A demo-mode service container (no FastAPI needed) for contract / report tests."""
    from pathlib import Path
    from app.services import Container
    from app.settings import Settings
    st = Settings(data_mode="demo", backend="memory", database_url=None, state="telangana", cors_origins=[],
                  show_record_points=True, contact_email=None, ml_model_dir=Path("/nonexistent"),
                  min_zoom_potential=8, max_cells=8000, rate_limit_per_min=60,
                  ai_provider="openai-compatible", ai_base_url="https://api.openai.com/v1",
                  ai_model="gpt-4o-mini", ai_api_key=None)
    return Container(st, cfg, demo_repo, None)
