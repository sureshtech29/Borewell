"""API contract tests that do not need FastAPI: the repository/service outputs must satisfy the response schemas."""
from __future__ import annotations

import re

import pytest

from app.ratelimit import RateLimiter
from app.reports.render import PdfUnavailable, html_to_pdf, render_report_html
from app.schemas import (AnalysisResponse, DatasetsOut, MetaOut, RegionItem, SearchItem)
from app.services import build_datasets, build_meta, run_analysis
from app.settings import load_settings

POINTS = {
    "inside": (17.45, 78.35),
    "outside": (12.90, 77.60),          # Bengaluru: outside Telangana coverage
    "edge": (17.001, 77.551),
}


def test_meta_and_datasets_match_schema(container):
    m = MetaOut.model_validate(build_meta(container))
    assert m.data_mode == "demo"
    assert [x.key for x in m.legend] == ["high", "moderate", "low", "very_low", "insufficient_data"]
    assert [x.color for x in m.legend] == ["#1E6FD9", "#2E9E4F", "#F2C230", "#D64545", "#9AA3AD"]
    d = DatasetsOut.model_validate(build_datasets(container))
    assert d.sources and all(s.is_demo for s in d.sources)
    assert all(s.name.en.startswith("DEMO") for s in d.sources)


@pytest.mark.parametrize("q", ["Patan", "పటాన్", "5000", "500072", "Sanga", "Telangana"])
def test_search_results_match_schema(container, q):
    items = container.repo.search(q, 10)
    for it in items:
        SearchItem.model_validate(it)


def test_search_finds_pincode_500032(container):
    pins = container.repo.search("500032", 10)
    assert len(pins) == 2
    assert {item["type"] for item in pins} == {"pincode"}
    assert {item["pincode"] for item in pins} == {"500032"}
    assert {item["name"]["en"] for item in pins} == {
        "500032 - Gachibowli S.O", "500032 - MANUU S.O"
    }
    assert all(item["context"]["en"].startswith("Rangareddy") for item in pins)
    assert all(item["in_coverage"] for item in pins)


def test_search_finds_known_demo_places(container):
    assert any(i["type"] == "mandal" for i in container.repo.search("Patancheru", 10))
    pins = container.repo.search("5000", 10)
    assert pins and all(i["type"] in ("pincode", "village", "mandal", "district") for i in pins)


def test_cascading_regions_match_schema(container):
    states = container.repo.regions("state", None)
    districts = container.repo.regions("district", None)
    assert districts
    for r in states + districts:
        RegionItem.model_validate(r)
    first = districts[0]
    for r in container.repo.regions("mandal", first["id"]):
        RegionItem.model_validate(r)


@pytest.mark.parametrize("name", list(POINTS))
def test_analysis_matches_schema(container, name):
    lat, lon = POINTS[name]
    a = run_analysis(container, lat, lon, 25)
    AnalysisResponse.model_validate(a)
    assert a["is_demo"] is True and a["disclaimer"]["en"] and a["disclaimer"]["te"]
    if name == "outside":
        assert a["status"] == "out_of_coverage" and a["potential"]["class"] == "insufficient_data"
        assert a["drilling_depth"] is None or a["drilling_depth"]["available"] is False


def test_geojson_layers(container):
    bbox = (78.0, 17.3, 78.3, 17.6)
    for fc in (container.repo.potential_geojson(bbox, 8000), container.repo.wells_geojson(bbox, 3000),
               container.repo.borewells_geojson(bbox, 3000), container.repo.coverage_geojson()):
        assert fc["type"] == "FeatureCollection"
    pot = container.repo.potential_geojson(bbox, 8000)["features"]
    assert pot and {f["properties"]["class"] for f in pot} <= {"high", "moderate", "low", "very_low", "insufficient_data"}


def test_borewell_layer_never_exposes_owner_fields(container):
    feats = container.repo.borewells_geojson((77.5, 17.0, 79.1, 18.3), 3000)["features"]
    banned = {"owner", "owner_name", "name", "phone", "address", "survey_no", "survey_number"}
    assert feats and all(not (banned & set(f["properties"])) for f in feats)


@pytest.mark.parametrize("lang", ["en", "te"])
@pytest.mark.parametrize("name", list(POINTS))
def test_report_html_renders(container, name, lang):
    lat, lon = POINTS[name]
    a = run_analysis(container, lat, lon, None)
    html = render_report_html(a, lang)
    assert a["disclaimer"][lang] in html
    assert "DEMONSTRATION DATA" in html or lang == "te"   # Telugu watermark text is checked below
    assert a["potential"]["label"][lang] in html or a["status_title"][lang] in html
    assert "None" not in re.sub(r"<style.*?</style>", "", html, flags=re.S)
    assert "{{" not in html and "{%" not in html
    # every unformatted label placeholder like {r} / {n} must have been filled
    assert not re.search(r"\{[a-z_]+\}", re.sub(r"<style.*?</style>", "", html, flags=re.S))


def test_report_telugu_uses_telugu_text_and_font_stack(container):
    a = run_analysis(container, *POINTS["inside"], None)
    html = render_report_html(a, "te")
    assert 'lang="te"' in html and "Noto Sans Telugu" in html
    assert a["potential"]["label"]["te"] in html and "తెలంగాణ" in html
    # real (non-demo) data must not carry the demo watermark
    a2 = dict(a, is_demo=False, warnings=[w for w in a["warnings"] if w["code"] != "demo_data"])
    assert "DEMONSTRATION" not in render_report_html(a2, "en")


def test_pdf_degrades_gracefully_without_weasyprint():
    try:
        import weasyprint  # noqa: F401
    except Exception:
        with pytest.raises(PdfUnavailable):
            html_to_pdf("<p>x</p>")
    else:
        assert html_to_pdf("<p>x</p>").startswith(b"%PDF")


def test_rate_limiter_window():
    rl = RateLimiter(3, 60)
    assert [rl.allow("a", now=t) for t in (0, 1, 2, 3)] == [True, True, True, False]
    assert rl.allow("b", now=3) and rl.allow("a", now=61)


def test_settings_guard_rails(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_DATA_BACKEND", "memory")
    with pytest.raises(ValueError):
        load_settings()                               # production must never run on synthetic in-memory data
    monkeypatch.setenv("APP_DATA_MODE", "demo")
    monkeypatch.setenv("APP_DATA_BACKEND", "postgis")
    with pytest.raises(ValueError):
        load_settings()                               # postgis needs DATABASE_URL


TREND_SENTENCES = {"falling": "Water level is falling by", "rising": "Water level is rising by",
                   "steady": "Water level has been roughly steady"}


@pytest.mark.parametrize("trend,key,te_word", [(0.4, "falling", "తగ్గుతోంది"), (-0.4, "rising", "పెరుగుతోంది"),
                                               (0.01, "steady", "స్థిరంగా")])
def test_report_trend_wording_follows_sign_convention(container, trend, key, te_word):
    """trend_m_per_yr > 0 means the water table is DEEPENING, i.e. the water level is FALLING."""
    a = run_analysis(container, 17.05, 78.75)
    assert a["water_table"]["available"], "fixture point must have a water table"
    a["water_table"]["trend_m_per_yr"] = trend
    en, te = render_report_html(a, "en"), render_report_html(a, "te")
    assert TREND_SENTENCES[key] in en and te_word in te
    for other, sentence in TREND_SENTENCES.items():
        if other != key:
            assert sentence not in en
    assert "m/yr" not in en


def test_postgis_state_info_survives_an_empty_production_database(cfg):
    """A fresh production database has no `states` row yet: the API must start and report 'planned', not crash."""
    from app.repository.postgis import PostgisRepository

    class EmptyDb(PostgisRepository):
        def __init__(self):
            self.cfg, self.state = cfg, "telangana"

        def _one(self, *a, **k):
            return None

    info = EmptyDb().state_info()
    assert info["coverage_status"] == "planned" and info["coverage_bbox"] is None
    assert info["code"] == "TG" and info["name"]["te"] and info["bounds"] == cfg.map_bounds
