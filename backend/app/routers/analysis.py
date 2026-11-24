from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas import AnalysisResponse
from ..services import Container, run_analysis
from .common import get_container, limit_requests

router = APIRouter()


@router.get("/analyze", response_model=AnalysisResponse, response_model_by_alias=True, tags=["analysis"],
            dependencies=[Depends(limit_requests)])
def analyze_location(lat: float = Query(..., ge=-90, le=90, description="latitude, decimal degrees (WGS 84)"),
                     lon: float = Query(..., ge=-180, le=180, description="longitude, decimal degrees (WGS 84)"),
                     accuracy_m: Optional[float] = Query(None, ge=0, le=1_000_000,
                                                         description="GPS accuracy in metres, if known"),
                     c: Container = Depends(get_container)):
    """Groundwater POTENTIAL analysis for one location. Never a guarantee that water exists."""
    return run_analysis(c, lat, lon, accuracy_m)


class PlotRankIn(BaseModel):
    """A user-drawn farm boundary in WGS84 (latitude, longitude) pairs."""
    boundary: list[tuple[float, float]] = Field(min_length=3, max_length=20)
    grid_size: int = Field(default=3, ge=2, le=5)

    @model_validator(mode="after")
    def validate_boundary(self):
        for lat, lon in self.boundary:
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Boundary coordinates must be valid WGS84 latitude/longitude")
        lats = [p[0] for p in self.boundary]
        lons = [p[1] for p in self.boundary]
        if max(lats) - min(lats) > 0.1 or max(lons) - min(lons) > 0.1:
            raise ValueError("Plot boundary is too large; submit a smaller farm area")
        return self


def _inside_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, (yi, xi) in enumerate(polygon):
        yj, xj = polygon[j]
        crosses = ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi)
        if crosses:
            inside = not inside
        j = i
    return inside


@router.post("/plot-rank", tags=["analysis"], dependencies=[Depends(limit_requests)])
def rank_plot_sites(payload: PlotRankIn, c: Container = Depends(get_container)):
    """Rank sample points within a user-drawn plot using the existing point-analysis engine.

    This is a screening aid only: it does not resolve within-field fractures or replace
    a qualified geophysical survey.
    """
    boundary = payload.boundary
    lats, lons = [p[0] for p in boundary], [p[1] for p in boundary]
    south, north, west, east = min(lats), max(lats), min(lons), max(lons)
    candidates = []
    # Sample a bounded regular grid; retain only points inside the polygon.
    for row in range(1, payload.grid_size + 1):
        for col in range(1, payload.grid_size + 1):
            lat = south + (north - south) * row / (payload.grid_size + 1)
            lon = west + (east - west) * col / (payload.grid_size + 1)
            if _inside_polygon(lat, lon, boundary):
                result = run_analysis(c, lat, lon)
                potential = result.get("potential") or {}
                confidence = result.get("confidence") or {}
                candidates.append({
                    "id": len(candidates) + 1, "lat": round(lat, 6), "lon": round(lon, 6),
                    "status": result.get("status"), "data_mode": result.get("data_mode"),
                    "is_demo": result.get("is_demo", True),
                    "potential_class": potential.get("class", "insufficient_data"),
                    "potential_label": potential.get("label"), "score": potential.get("score"),
                    "confidence_level": confidence.get("level", "low"),
                    "confidence_score": confidence.get("score"),
                    "drilling_depth": result.get("drilling_depth"),
                })
    if not candidates:
        raise HTTPException(status_code=422, detail="No sample points fell inside this boundary. Draw a larger plot boundary.")
    candidates.sort(key=lambda x: (x["score"] is not None, x["score"] if x["score"] is not None else -1), reverse=True)
    for rank, item in enumerate(candidates, 1):
        item["rank"] = rank
    return {
        "status": "ok", "data_mode": c.repo.data_mode, "is_demo": c.repo.data_mode == "demo",
        "candidate_count": len(candidates), "candidates": candidates,
        "method": "Existing point-analysis engine sampled on a regular grid inside the supplied plot boundary.",
        "limitations": [
            "Rankings are screening estimates, not a guarantee of groundwater or drilling success.",
            "The sample grid cannot identify plot-scale fractures or replace VES/ERT and hydrogeologist review.",
            "In demo mode, every result is synthetic and must not be used for real drilling decisions.",
        ],
    }
