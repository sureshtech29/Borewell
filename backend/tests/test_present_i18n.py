import json
import random
import re
from pathlib import Path

import pytest

from app import i18n
from app.engine import analyze
from app.engine.types import Radii
from app.present import present
from app.schemas import AnalysisResponse
from tests.conftest import make_bw, make_ctx

TELUGU = re.compile(r"[ఀ-౿]")
R = Radii()


def test_every_message_has_both_languages_with_matching_placeholders():
    for table in (i18n.MESSAGES, i18n.LABELS, i18n.GW_CATEGORY):
        for key, v in table.items():
            assert set(v) == {"en", "te"}, key
            assert v["en"].strip() and v["te"].strip(), key
            assert i18n.placeholders(v["en"]) == i18n.placeholders(v["te"]), f"placeholder mismatch in {key}"


def test_telugu_text_is_actually_telugu():
    for key, v in i18n.MESSAGES.items():
        assert TELUGU.search(v["te"]), f"{key}: Telugu text contains no Telugu script"
    for key, v in i18n.LABELS.items():
        assert TELUGU.search(v["te"]), key


def test_config_labels_are_bilingual(cfg):
    for fk, f in cfg.factors.items():
        assert TELUGU.search(f["label"]["te"]), fk
        for ck, c in f.get("classes", {}).items():
            assert TELUGU.search(c["label"]["te"]), f"{fk}.{ck}"
    for k, c in cfg.classes.items():
        assert TELUGU.search(c["label"]["te"]), k


def test_all_engine_message_codes_exist():
    src = (Path(__file__).resolve().parents[1] / "app" / "engine" / "analyze.py").read_text()
    codes = set(re.findall(r'Msg\("([a-z_\.]+)"', src))
    codes |= {"gw_over_exploited", "gw_critical", "gw_saline"}               # built dynamically as f"gw_{cat}"
    missing = [c for c in codes if c not in i18n.MESSAGES]
    assert not missing, missing


def test_render_substitutes_params_and_reason_variants():
    t = i18n.render("gap_water_level", {"reason": "too_few_wells", "radius_km": 15.0})
    assert "15" in t["en"] and "15" in t["te"] and "{" not in t["en"] + t["te"]
    assert i18n.render("gap_depth_range", {"reason": "no_records"})["en"].startswith("No nearby")
    assert i18n.render("nope") == {"en": "nope", "te": "nope"}


def _validate(res, cfg, **kw):
    d = present(res, cfg, **kw)
    AnalysisResponse.model_validate(d)                # extra fields / wrong types would raise
    json.dumps(d, ensure_ascii=False)
    return d


def test_presented_payload_matches_schema_everywhere(demo_repo, cfg, today):
    random.seed(11)
    seen = set()
    pts = [(random.uniform(17.0, 18.3), random.uniform(77.55, 79.05)) for _ in range(40)] + [(10.0, 80.0), (17.97, 79.59)]
    for lat, lon in pts:
        res = analyze(demo_repo.point_context(lat, lon, R), cfg, today=today)
        d = _validate(res, cfg)
        seen.add(d["status"])
        # no unresolved placeholders in any rendered message
        for key in ("warnings", "data_gaps", "recommendations"):
            for m in d[key]:
                assert "{" not in m["text"]["en"] and "{" not in m["text"]["te"], m
    assert {"ok", "out_of_coverage"} <= seen


def test_insufficient_data_payload(cfg, today):
    d = _validate(analyze(make_ctx(lithology=None), cfg, today=today), cfg)
    assert d["status"] == "insufficient_data" and d["potential"]["class"] == "insufficient_data"
    assert d["potential"]["color"] == "#9AA3AD" and d["confidence"] is None and d["potential"]["score"] is None
    assert d["potential"]["insufficient_reason"]["en"]


def test_colours_match_specification(cfg):
    want = {"high": "#1E6FD9", "moderate": "#2E9E4F", "low": "#F2C230", "very_low": "#D64545", "insufficient_data": "#9AA3AD"}
    assert {k: cfg.class_color(k) for k in want} == want                      # blue, green, yellow, red, grey


def test_individual_borewell_coordinates_are_not_exposed(cfg, today):
    bws = [make_bw(i, lat=17.5 + i * 0.00123, lon=78.0 + i * 0.00077) for i in range(1, 7)]
    d = _validate(analyze(make_ctx(borewells=bws), cfg, today=today), cfg)
    blob = json.dumps(d)
    for b in bws:
        assert str(b.lat) not in blob and str(b.lon) not in blob


def test_demo_payload_is_labelled(demo_repo, cfg, today):
    d = _validate(analyze(demo_repo.point_context(17.62, 78.09, R), cfg, today=today), cfg)
    assert d["is_demo"] and d["data_mode"] == "demo" and d["warnings"][0]["code"] == "demo_data"
    assert all(s["is_demo"] and s["name"]["en"].startswith("DEMO") for s in d["sources"])
