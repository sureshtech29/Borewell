from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.routers.analysis import PlotRankIn, rank_plot_sites


def test_plot_boundary_validation_rejects_invalid_coordinates():
    with pytest.raises(ValidationError):
        PlotRankIn(boundary=[(17.0, 78.0), (17.1, 78.1), (91.0, 78.0)])


def test_plot_boundary_validation_rejects_oversized_area():
    with pytest.raises(ValidationError):
        PlotRankIn(boundary=[(17.0, 78.0), (17.2, 78.0), (17.2, 78.1)])


def test_plot_ranking_returns_ordered_candidates_and_demo_warning(container):
    request = PlotRankIn(boundary=[(17.40, 78.30), (17.40, 78.36), (17.46, 78.36), (17.46, 78.30)])
    result = rank_plot_sites(request, container)
    assert result["status"] == "ok"
    assert result["is_demo"] is True
    assert 1 <= result["candidate_count"] <= 9
    assert [x["rank"] for x in result["candidates"]] == list(range(1, result["candidate_count"] + 1))
    scores = [x["score"] for x in result["candidates"] if x["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    assert all(x["is_demo"] for x in result["candidates"])
    assert any("synthetic" in x.lower() for x in result["limitations"])
