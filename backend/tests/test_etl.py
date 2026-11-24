"""ETL helpers and loaders, tested with a recording fake database (no PostgreSQL / psycopg needed)."""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.etl import imd, load
from scripts.etl.mapping import map_alias, outcome_from_yield, parse_thresholds, season_for


class FakeDb:
    def __init__(self, source_is_demo=False, source_exists=True):
        self.calls, self.exe_many = [], []
        self.source_row = (source_is_demo,) if source_exists else None
        self.committed = self.rolled_back = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        row = self.source_row if "FROM data_sources" in sql else None
        return type("R", (), {"fetchone": lambda s: row})()

    def executemany(self, sql, rows):
        self.exe_many.append((sql, list(rows)))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def assert_placeholders_match(db):
    for sql, rows in db.exe_many:
        for r in rows:
            assert sql.count("%s") == len(r), sql[:80]
    for sql, params in db.calls:
        if params is not None:
            assert sql.count("%s") == len(params), sql[:80]


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# ----------------------------------------------------------------------------------- pure helpers
def test_alias_longest_match_wins(cfg):
    soil = cfg.section("etl")["soil_aliases"]
    assert map_alias("Clay loam", soil) == "clay_loam"          # not 'loam'
    assert map_alias("SANDY LOAM (deep)", soil) == "sandy_loam"  # not 'sandy'
    assert map_alias("Black cotton soil", soil) == "black_cotton"
    assert map_alias("pegmatite", cfg.section("etl")["lithology_aliases"]) is None
    assert map_alias(None, soil) is None


def test_all_alias_targets_are_real_classes(cfg):
    etl = cfg.section("etl")
    for alias_key, factor in (("lithology_aliases", "lithology"), ("aquifer_aliases", "aquifer"), ("soil_aliases", "soil")):
        assert set(etl[alias_key].values()) <= set(cfg.factors[factor]["classes"]), alias_key


def test_season_and_outcome_helpers():
    assert [season_for(date(2024, m, 1)) for m in (1, 5, 8, 11)] == ["winter", "pre_monsoon", "monsoon", "post_monsoon"]
    thr = parse_thresholds("low<60,moderate<180")
    assert [outcome_from_yield(y, thr) for y in (0, 30, 100, 400)] == ["dry", "low", "moderate", "good"]
    for bad in ("low<60", "moderate<10,low<20", "good<5,low<1", "low<200,moderate<100"):
        with pytest.raises(ValueError):
            parse_thresholds(bad)


# ----------------------------------------------------------------------------------- IMD reader
def _write_grd(path, year, fill):
    days = 366 if year % 4 == 0 else 365
    a = np.full((days, imd.NLAT, imd.NLON), imd.UNDEF, dtype="<f4")
    a[:, 10, 20] = fill
    a.tofile(path)


@pytest.mark.parametrize("year", [2023, 2024])
def test_imd_annual_and_monsoon_totals(tmp_path, year):
    p = tmp_path / f"Rainfall_ind{year}_rfp25.grd"
    _write_grd(p, year, 2.0)
    ann, mon = imd.annual_totals(imd.read_grd(p, year), year)
    days = 366 if year == 2024 else 365
    assert ann[10, 20] == pytest.approx(2.0 * days)
    assert mon[10, 20] == pytest.approx(2.0 * 122)               # Jun 1 - Sep 30
    assert np.isnan(ann[0, 0]) and np.isnan(mon[0, 0])           # undefined cells stay undefined


def test_imd_rejects_wrong_size_and_year(tmp_path):
    p = tmp_path / "x.grd"
    _write_grd(p, 2023, 1.0)
    with pytest.raises(ValueError):
        imd.read_grd(p, 2024)                                    # 2023 file read as a leap year
    p.write_bytes(b"\x00" * 1000)
    with pytest.raises(ValueError):
        imd.read_grd(p, 2023)


def test_imd_cell_with_many_missing_days_is_not_used(tmp_path):
    p = tmp_path / "r.grd"
    _write_grd(p, 2023, 1.0)
    a = imd.read_grd(p, 2023)
    a[:30, 10, 20] = np.nan
    ann, _ = imd.annual_totals(a, 2023)
    assert np.isnan(ann[10, 20])


# ----------------------------------------------------------------------------------- loaders
def test_source_rejects_demo_names_and_future_dates():
    db = FakeDb()
    kw = dict(name_en="CGWB water levels", publisher="CGWB", kind="water_level", license="GODL-India", last_updated=date(2025, 5, 1))
    assert load.cmd_source(db, source_id="cgwb_gwl", **kw).ok == 1
    assert load.cmd_source(db, source_id="demo_wells", **kw).errors
    assert load.cmd_source(db, source_id="x", **{**kw, "last_updated": date.today() + timedelta(days=2)}).errors
    assert load.cmd_source(db, source_id="x", **{**kw, "kind": "nonsense"}).errors
    assert_placeholders_match(db)


def test_loading_requires_a_registered_real_source(cfg, tmp_path):
    f = write(tmp_path, "b.csv", "lat,lon,depth_ft,outcome\n17.4,78.4,300,good\n")
    assert "not registered" in load.cmd_borewells(FakeDb(source_exists=False), cfg, path=f, source_id="s").errors[0]
    assert "demo source" in load.cmd_borewells(FakeDb(source_is_demo=True), cfg, path=f, source_id="s").errors[0]


def test_wells_valid_and_invalid_rows(cfg, tmp_path):
    st = write(tmp_path, "st.csv", "station_code,name,lat,lon,agency,well_type\nW1,Alpha,17.4,78.4,CGWB,piezometer\nW2,Beta,17.5,78.5,CGWB,dug_well\n")
    rd = write(tmp_path, "rd.csv", "station_code,date,depth_to_water_m\nW1,2024-05-20,12.5\nW1,2024-11-15,8.2\nW2,2024-05-21,9.0\n")
    db = FakeDb()
    rep = load.cmd_wells(db, cfg, stations=st, readings=rd, source_id="s")
    assert not rep.errors and rep.ok == 5
    seasons = [r[1] for r in db.exe_many[1][1]]
    assert seasons == ["pre_monsoon", "post_monsoon", "pre_monsoon"]
    assert_placeholders_match(db)

    bad = write(tmp_path, "bad.csv", "station_code,date,depth_to_water_m\nW9,2024-05-20,12.5\nW1,2999-01-01,5\nW1,2024-05-20,-3\nW1,20-05-2024,abc\n")
    db2 = FakeDb()
    rep = load.cmd_wells(db2, cfg, stations=st, readings=bad, source_id="s")
    assert len(rep.errors) == 4 and rep.errors[0].startswith("row 2")
    assert db2.exe_many == []                                      # nothing is written when rows are invalid


def test_wells_outside_state_bounds_are_rejected(cfg, tmp_path):
    st = write(tmp_path, "st.csv", "station_code,lat,lon\nW1,78.4,17.4\n")       # lat/lon swapped
    rd = write(tmp_path, "rd.csv", "station_code,date,depth_to_water_m\nW1,2024-05-20,12.5\n")
    assert "swapped" in load.cmd_wells(FakeDb(), cfg, stations=st, readings=rd, source_id="s").errors[0]


def test_borewells_need_an_outcome_or_explicit_yield_thresholds(cfg, tmp_path):
    f = write(tmp_path, "b.csv", "lat,lon,depth_ft,yield_lpm\n17.4,78.4,300,100\n17.41,78.41,250,0\n")
    assert load.cmd_borewells(FakeDb(), cfg, path=f, source_id="s").errors
    db = FakeDb()
    rep = load.cmd_borewells(db, cfg, path=f, source_id="s", yield_thresholds="low<60,moderate<180")
    assert not rep.errors and [r[9] for r in db.exe_many[0][1]] == ["moderate", "dry"]
    assert_placeholders_match(db)


def test_borewells_reject_implausible_depth(cfg, tmp_path):
    f = write(tmp_path, "b.csv", "lat,lon,depth_ft,outcome\n17.4,78.4,3,good\n17.4,78.4,300,good\n")
    rep = load.cmd_borewells(FakeDb(), cfg, path=f, source_id="s")
    assert len(rep.errors) == 1 and "depth_ft" in rep.errors[0]


def test_borewell_loader_never_stores_personal_columns(cfg, tmp_path):
    f = write(tmp_path, "b.csv", "lat,lon,depth_ft,outcome,owner_name,phone\n17.4,78.4,300,good,Ravi Kumar,9999912345\n")
    db = FakeDb()
    rep = load.cmd_borewells(db, cfg, path=f, source_id="s")
    assert rep.ok == 1 and db.exe_many                                  # non-vacuous: a row WAS inserted
    sql, rows = db.exe_many[0]
    assert "owner" not in sql and "phone" not in sql
    assert not any("Ravi" in str(v) or "9999912345" in str(v) for r in rows for v in r)


def test_ves_validates_suitability(cfg, tmp_path):
    f = write(tmp_path, "v.csv", "lat,lon,method,suitability,survey_year\n17.4,78.4,VES-Schlumberger,good,2015\n17.4,78.4,ERT,excellent,2015\n")
    rep = load.cmd_ves(FakeDb(), cfg, path=f, source_id="s")
    assert len(rep.errors) == 1 and "suitability" in rep.errors[0]


def test_grid_loader_checks_factor_keys_and_keeps_missing_values_null(cfg, tmp_path):
    f = write(tmp_path, "g.csv", "lon,lat,res_m,elevation_m,slope_deg,tpi_m,drainage_density,lineament_density\n78.4,17.4,500,520,2.5,,1.2,\n")
    assert load.cmd_grid(FakeDb(), cfg, path=f, source_map={"nonsense": "s"}).errors
    db = FakeDb()
    rep = load.cmd_grid(db, cfg, path=f, source_map={"slope": "s"})
    assert not rep.errors
    row = db.exe_many[0][1][0]
    assert row[8:13] == (520.0, 2.5, None, 1.2, None)               # blanks stay NULL - never filled in
    assert json.loads(row[13]) == {"slope": "s"}
    assert_placeholders_match(db)


def _geojson(tmp_path, props_list):
    sq = {"type": "Polygon", "coordinates": [[[78.0, 17.0], [78.1, 17.0], [78.1, 17.1], [78.0, 17.1], [78.0, 17.0]]]}
    return write(tmp_path, "g.geojson", json.dumps({"type": "FeatureCollection",
                 "features": [{"type": "Feature", "properties": p, "geometry": sq} for p in props_list]}))


def test_polygon_loader_maps_classes_and_reports_unmapped(cfg, tmp_path):
    f = _geojson(tmp_path, [{"LITH": "Granitic gneiss"}, {"LITH": "Pegmatite vein"}])
    db = FakeDb()
    rep = load.cmd_polygons(db, cfg, layer="geology", path=f, source_id="s", field="LITH")
    assert rep.errors and "Pegmatite" in rep.errors[0] and db.exe_many == []
    db = FakeDb()
    rep = load.cmd_polygons(db, cfg, layer="geology", path=f, source_id="s", field="LITH", allow_unmapped=True)
    assert rep.ok == 1 and rep.warnings and db.exe_many[0][1][0][1] == "granite_gneiss"
    assert_placeholders_match(db)


def test_polygon_loader_rejects_non_wgs84(cfg, tmp_path):
    p = write(tmp_path, "g.geojson", json.dumps({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32644"}}, "features": []}))
    with pytest.raises(ValueError):
        load.cmd_polygons(FakeDb(), cfg, layer="soil", path=p, source_id="s", field="X")


def test_finish_rolls_back_on_errors_and_on_dry_run():
    from scripts.etl.mapping import Report
    db = FakeDb()
    assert load._finish(db, Report(errors=["row 2: bad"]), dry_run=False, skip_invalid=False, what="t") is False and db.rolled_back
    db = FakeDb()
    assert load._finish(db, Report(ok=3), dry_run=True, skip_invalid=False, what="t") and db.rolled_back and not db.committed
    db = FakeDb()
    assert load._finish(db, Report(ok=3), dry_run=False, skip_invalid=False, what="t") and db.committed
