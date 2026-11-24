"""Plain data containers shared by the analysis engine and the repositories.

The engine is deliberately free of web/database imports so it can be unit-tested
and reused by batch jobs (map pre-computation, ML training).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    name_en: str
    publisher: str
    layer_kind: str
    name_te: Optional[str] = None
    url: Optional[str] = None
    license: Optional[str] = None
    retrieved_on: Optional[date] = None
    data_last_updated: Optional[date] = None
    is_demo: bool = False
    notes: Optional[str] = None


@dataclass(frozen=True)
class Reading:
    measured_on: date
    season: str                      # pre_monsoon | monsoon | post_monsoon | winter
    depth_to_water_m: float          # metres below ground level


@dataclass
class ObservationWell:
    well_id: int
    station_code: str
    lat: float
    lon: float
    readings: list[Reading] = field(default_factory=list)
    name: Optional[str] = None
    agency: Optional[str] = None
    source_id: Optional[str] = None


@dataclass
class BorewellRecord:
    borewell_id: int
    lat: float
    lon: float
    depth_ft: float
    outcome: str                     # dry | low | moderate | good
    yield_lpm: Optional[float] = None
    drilled_year: Optional[int] = None
    location_accuracy_m: Optional[int] = None
    source_id: Optional[str] = None


@dataclass
class VesSurvey:
    survey_id: int
    lat: float
    lon: float
    method: str
    suitability: str                 # good | moderate | poor
    survey_year: Optional[int] = None
    weathered_thickness_m: Optional[float] = None
    fracture_zone_top_m: Optional[float] = None
    fracture_zone_bottom_m: Optional[float] = None
    note: Optional[str] = None
    source_id: Optional[str] = None


@dataclass
class ClassifiedUnit:
    """Result of a point-in-polygon lookup in a thematic layer."""
    class_key: str
    name: Optional[str]
    source_id: str


@dataclass
class FeatureCell:
    cell_id: int
    elevation_m: Optional[float] = None
    slope_deg: Optional[float] = None
    tpi_m: Optional[float] = None
    drainage_density: Optional[float] = None
    lineament_density: Optional[float] = None
    rainfall_normal_mm: Optional[float] = None
    rainfall_cv: Optional[float] = None
    source_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class RegionInfo:
    state_code: str
    state_en: str
    state_te: Optional[str] = None
    district_en: Optional[str] = None
    district_te: Optional[str] = None
    mandal_en: Optional[str] = None
    mandal_te: Optional[str] = None
    village_en: Optional[str] = None
    village_te: Optional[str] = None
    method: str = "polygon"          # polygon | nearest_place
    nearest_place_km: Optional[float] = None
    gw_category: Optional[str] = None
    gw_category_year: Optional[int] = None
    gw_category_source_id: Optional[str] = None


@dataclass
class PointContext:
    """Everything the engine needs to know about one location."""
    lat: float
    lon: float
    in_coverage: bool = False
    data_mode: str = "demo"
    region: Optional[RegionInfo] = None
    cell: Optional[FeatureCell] = None
    lithology: Optional[ClassifiedUnit] = None
    aquifer: Optional[ClassifiedUnit] = None
    soil: Optional[ClassifiedUnit] = None
    wells: list[ObservationWell] = field(default_factory=list)
    borewells: list[BorewellRecord] = field(default_factory=list)
    ves: list[VesSurvey] = field(default_factory=list)
    rainfall_years: list[tuple[int, float]] = field(default_factory=list)   # (year, annual_mm)
    rainfall_source_id: Optional[str] = None
    sources: dict[str, SourceRef] = field(default_factory=dict)


@dataclass(frozen=True)
class Radii:
    """Search radii the repository must honour when building a PointContext."""
    wells_km: float = 15.0
    borewells_km: float = 10.0
    ves_km: float = 2.0
    rainfall_years: int = 15


@dataclass
class Msg:
    """A user-facing message identified by a code (text lives in app/i18n.py)."""
    code: str
    params: dict = field(default_factory=dict)
