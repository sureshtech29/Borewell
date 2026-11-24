"""Repository interface. Two implementations:

* MemoryRepository  - synthetic demo dataset, no database (tests, quick local demo)
* PostgisRepository - PostgreSQL/PostGIS (demo seed or real production data)

Both return the same shapes, so the engine, routers and PDF code do not care.
"""
from __future__ import annotations

from typing import Iterable, Optional, Protocol

from ..engine.types import PointContext, Radii


class Repository(Protocol):
    data_mode: str                      # 'demo' | 'production'

    def ping(self) -> bool: ...

    def state_info(self) -> dict:
        """{code, name:{en,te}, coverage_status, bounds, coverage_bbox}"""

    def point_context(self, lat: float, lon: float, radii: Radii) -> PointContext: ...

    def search(self, q: str, limit: int = 10) -> list[dict]: ...

    def regions(self, level: str, parent_id: Optional[int]) -> list[dict]: ...

    def potential_geojson(self, bbox: tuple[float, float, float, float], limit: int) -> dict: ...

    def wells_geojson(self, bbox: tuple[float, float, float, float], limit: int) -> dict: ...

    def borewells_geojson(self, bbox: tuple[float, float, float, float], limit: int) -> dict: ...

    def coverage_geojson(self) -> dict: ...

    def datasets(self) -> list[dict]: ...

    def layer_counts(self) -> dict[str, int]: ...

    def save_contact(self, name: str, email: Optional[str], phone: Optional[str], message: str,
                     lang: Optional[str]) -> int: ...

    def training_points(self) -> Iterable[tuple[float, float, str]]:
        """(lat, lon, outcome) for every usable historical borewell record."""

    def cell_centroids(self) -> Iterable[tuple[int, float, float]]:
        """(cell_id, lat, lon) for every feature-grid cell (batch pre-computation)."""


def empty_fc() -> dict:
    return {"type": "FeatureCollection", "features": []}
