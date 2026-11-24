"""compute_potential / train_model driven through a fake PostGIS repository built from the demo dataset."""
from __future__ import annotations

import json
from datetime import date

import pytest

from scripts import compute_potential


class FakePostgis:
    """Mimics the batch API of PostgisRepository on top of the in-memory demo repository."""
    written: list = []

    def __init__(self, url, cfg, mode, **kw):
        from tests.conftest import _demo_repo_singleton
        self.m = _demo_repo_singleton(cfg)

    def load_all_wells(self, today):
        return self.m.ds.wells

    def iter_regional_inputs(self, batch=2000):
        cells = self.m.ds.cells
        for i in range(0, len(cells), batch):
            out = []
            for gc in cells[i:i + batch]:
                lat, lon = gc.centroid
                out.append((lat, lon, gc.cell, self.m._geo.lookup(lat, lon), self.m._aq.lookup(lat, lon), self.m._soil.lookup(lat, lon)))
            yield out

    def write_potential(self, rows):
        FakePostgis.written.extend(rows)

    def close(self):
        pass


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "demo")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("APP_DATA_BACKEND", "postgis")
    FakePostgis.written = []
    monkeypatch.setattr(compute_potential, "PostgisRepository", FakePostgis)


def test_compute_potential_matches_the_live_map_layer(env, demo_repo, capsys):
    assert compute_potential.main(["--batch", "1000"]) == 0
    rows = FakePostgis.written
    live = {gc.cell.cell_id: r for gc, r in demo_repo.potential_cells(date.today())}
    assert len(rows) == len(live) == 4875
    for r in rows[:: 97]:
        assert r["klass"] == live[r["cell_id"]].klass
        assert (r["score"] is None) == (live[r["cell_id"]].score is None)
        assert set(json.loads(r["factors"])) == {"lithology", "aquifer", "soil", "slope", "drainage_density", "lineament_density",
                                                  "rainfall", "topographic_position", "water_level"}
    assert {r["klass"] for r in rows} == {x.klass for x in live.values()}
    assert "written" in capsys.readouterr().out


def test_dry_run_writes_nothing(env):
    assert compute_potential.main(["--dry-run"]) == 0 and FakePostgis.written == []


def test_requires_postgis_backend(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_DATA_BACKEND", raising=False)
    monkeypatch.setenv("APP_DATA_MODE", "demo")
    assert compute_potential.main([]) == 2
