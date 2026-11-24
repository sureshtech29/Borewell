from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas import DatasetsOut, HealthOut, MetaOut, RegionItem, SearchItem
from ..services import Container, build_datasets, build_meta
from .common import get_container, limit_requests

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["meta"])
def health(c: Container = Depends(get_container)):
    if not c.repo.ping():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok", "data_mode": c.repo.data_mode, "backend": c.settings.backend}


@router.get("/meta", response_model=MetaOut, tags=["meta"])
def meta(c: Container = Depends(get_container)):
    """Everything the web app needs at start-up: mode, legend, coverage, settings."""
    return build_meta(c)


@router.get("/datasets", response_model=DatasetsOut, tags=["meta"])
def datasets(c: Container = Depends(get_container)):
    """Every data source in use, with publisher, retrieval date and last-updated date."""
    return build_datasets(c)


@router.get("/search", response_model=list[SearchItem], tags=["search"], dependencies=[Depends(limit_requests)])
def search(q: str = Query(..., min_length=2, max_length=80, description="place name (English or Telugu) or PIN code"),
           limit: int = Query(10, ge=1, le=25), c: Container = Depends(get_container)):
    return c.repo.search(q, limit)


@router.get("/regions", response_model=list[RegionItem], tags=["search"])
def regions(level: str = Query("district", pattern="^(state|district|mandal|village)$"),
            parent_id: Optional[int] = Query(None), c: Container = Depends(get_container)):
    """Cascading State -> District -> Mandal -> Village pick-lists."""
    return c.repo.regions(level, parent_id)
