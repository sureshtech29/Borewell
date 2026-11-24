"""In-memory dataset container (used by the demo generator, the memory repository
and the SQL exporter). Production data lives in PostGIS; this is the same shape."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..engine.types import BorewellRecord, FeatureCell, ObservationWell, SourceRef, VesSurvey


@dataclass
class Place:
    place_id: int
    level: str                         # district | mandal | village
    name_en: str
    name_te: str
    lat: float
    lon: float
    parent_id: Optional[int]
    source_id: str
    gw_category: Optional[str] = None
    gw_category_year: Optional[int] = None
    gw_category_source_id: Optional[str] = None


@dataclass
class Pin:
    pincode: str
    office_name: str
    lat: float
    lon: float
    district_place_id: Optional[int]
    source_id: str


@dataclass
class PolyUnit:
    gid: int
    class_key: str
    name: str
    ring: list[tuple[float, float]]    # (lon, lat), closed
    source_id: str

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.ring]
        ys = [p[1] for p in self.ring]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class GridCell:
    cell: FeatureCell
    lon0: float
    lat0: float
    lon1: float
    lat1: float

    @property
    def ring(self) -> list[tuple[float, float]]:
        return [(self.lon0, self.lat0), (self.lon1, self.lat0), (self.lon1, self.lat1),
                (self.lon0, self.lat1), (self.lon0, self.lat0)]

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.lat0 + self.lat1) / 2.0, (self.lon0 + self.lon1) / 2.0)   # (lat, lon)


@dataclass
class RainCell:
    key: str
    lat: float
    lon: float
    annual: dict[int, tuple[float, float]]   # year -> (annual_mm, monsoon_mm)


@dataclass
class Dataset:
    is_demo: bool
    anchor_date: date
    state_code: str
    state_en: str
    state_te: str
    coverage_bbox: tuple[float, float, float, float]       # lon0, lat0, lon1, lat1
    sources: dict[str, SourceRef] = field(default_factory=dict)
    places: list[Place] = field(default_factory=list)
    pins: list[Pin] = field(default_factory=list)
    geology: list[PolyUnit] = field(default_factory=list)
    soil: list[PolyUnit] = field(default_factory=list)
    aquifer: list[PolyUnit] = field(default_factory=list)
    grid_origin: tuple[float, float] = (0.0, 0.0)           # lon0, lat0
    grid_step: float = 0.02
    grid_shape: tuple[int, int] = (0, 0)                    # nrows, ncols
    cells: list[GridCell] = field(default_factory=list)     # row-major
    rain_cells: list[RainCell] = field(default_factory=list)
    wells: list[ObservationWell] = field(default_factory=list)
    borewells: list[BorewellRecord] = field(default_factory=list)
    ves: list[VesSurvey] = field(default_factory=list)
