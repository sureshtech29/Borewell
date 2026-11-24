from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..services import Container
from .common import get_container, limit_requests

router = APIRouter(prefix="/layers", tags=["layers"])
MAX_SPAN_DEG = 6.0


def parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        x0, y0, x1, y1 = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox must be 'minLon,minLat,maxLon,maxLat'")
    if not (-180 <= x0 < x1 <= 180 and -90 <= y0 < y1 <= 90):
        raise HTTPException(status_code=422, detail="bbox out of range or not ordered min<max")
    if (x1 - x0) > MAX_SPAN_DEG or (y1 - y0) > MAX_SPAN_DEG:
        raise HTTPException(status_code=422, detail=f"bbox too large (max {MAX_SPAN_DEG} degrees per side); zoom in")
    return x0, y0, x1, y1


@router.get("/potential", dependencies=[Depends(limit_requests)])
def potential(response: Response, bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
              c: Container = Depends(get_container)):
    """Regional groundwater-potential grid cells (the coloured map layer)."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return c.repo.potential_geojson(parse_bbox(bbox), c.settings.max_cells)


@router.get("/wells", dependencies=[Depends(limit_requests)])
def wells(response: Response, bbox: str = Query(...), c: Container = Depends(get_container)):
    """Groundwater monitoring wells (public CGWB / State network)."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return c.repo.wells_geojson(parse_bbox(bbox), 3000)


@router.get("/borewells", dependencies=[Depends(limit_requests)])
def borewells(response: Response, bbox: str = Query(...), c: Container = Depends(get_container)):
    """Individual historical borewell records. Hidden unless SHOW_RECORD_POINTS=true (privacy)."""
    box = parse_bbox(bbox)
    if not c.settings.show_record_points:
        return {"type": "FeatureCollection", "features": [], "hidden": True}
    response.headers["Cache-Control"] = "public, max-age=300"
    return c.repo.borewells_geojson(box, 3000)


@router.get("/coverage")
def coverage(response: Response, c: Container = Depends(get_container)):
    """Outline of the area for which data is loaded."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    return c.repo.coverage_geojson()
