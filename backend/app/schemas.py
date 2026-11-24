"""API schemas (also the source of the OpenAPI documentation).

Every response model forbids unknown fields, so if the presenter ever adds or renames a field
without updating this file, tests/test_present_i18n.py fails instead of the docs silently lying.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Text(Strict):
    """Bilingual text. Clients show text[lang]."""
    en: str
    te: str


class Message(Strict):
    code: str
    text: Text


# ----------------------------------------------------------------------------- analysis
PotentialClass = Literal["high", "moderate", "low", "very_low", "insufficient_data"]


class GwCategory(Strict):
    key: str
    label: Optional[Text] = None
    year: Optional[int] = None


class RegionOut(Strict):
    state: Text
    district: Optional[Text] = None
    mandal: Optional[Text] = None
    village: Optional[Text] = None
    method: Literal["polygon", "nearest_place"]
    nearest_place_km: Optional[float] = None
    gw_category: Optional[GwCategory] = None


class LocationOut(Strict):
    lat: float
    lon: float
    accuracy_m: Optional[float] = None
    region: Optional[RegionOut] = None


class PotentialOut(Strict):
    class_: PotentialClass = Field(alias="class")
    label: Text
    color: str
    score: Optional[float] = None
    regional_class: PotentialClass
    regional_label: Text
    regional_color: str
    regional_score: Optional[float] = None
    coverage: Optional[float] = None
    insufficient_reason: Optional[Text] = None
    note: Text
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ConfidenceComponentOut(Strict):
    key: str
    label: Text
    value: float
    weight: float


class ConfidenceOut(Strict):
    level: Literal["low", "medium", "high"]
    label: Text
    score: float
    capped: bool
    components: list[ConfidenceComponentOut]
    note: Text


class FactorOut(Strict):
    key: str
    label: Text
    kind: Literal["categorical", "numeric"]
    applicable: bool
    available: bool
    value: Optional[Any] = None
    unit: Optional[str] = None
    display: Optional[Text] = None
    score: Optional[float] = None
    weight: float
    effective_weight: float
    source_id: Optional[str] = None


class RangeOut(Strict):
    range_m: list[float]
    range_ft: list[int]
    estimate_m: Optional[float] = None
    estimate_ft: Optional[int] = None


class WellUsedOut(Strict):
    station_code: str
    distance_km: float
    pre_monsoon_m: Optional[float] = None
    post_monsoon_m: Optional[float] = None


class WaterTableOut(Strict):
    available: bool
    reason: Optional[str] = None
    radius_km: float
    n_wells: int
    nearest_km: Optional[float] = None
    pre_monsoon: Optional[RangeOut] = None
    post_monsoon: Optional[RangeOut] = None
    trend_m_per_yr: Optional[float] = None
    latest_reading_on: Optional[str] = None
    wells: list[WellUsedOut]
    note: Text


class DepthOut(Strict):
    available: bool
    reason: Optional[str] = None
    low_ft: Optional[float] = None
    high_ft: Optional[float] = None
    median_ft: Optional[float] = None
    n_productive: int
    n_dry: int
    dry_depth_max_ft: Optional[float] = None
    radius_km: Optional[float] = None
    n_required: int
    newest_record_year: Optional[int] = None
    note: Text


class OutcomeCount(Strict):
    key: Literal["dry", "low", "moderate", "good"]
    count: int
    label: Text


class VesOut(Strict):
    distance_km: float
    method: str
    survey_year: Optional[int] = None
    suitability: Literal["good", "moderate", "poor"]
    suitability_label: Text
    weathered_thickness_m: Optional[float] = None
    fracture_zone_top_m: Optional[float] = None
    fracture_zone_bottom_m: Optional[float] = None


class LocalEvidenceOut(Strict):
    used: bool
    radius_km: float
    n_records: int
    n_records_wider: int
    nearest_record_km: Optional[float] = None
    outcomes: list[OutcomeCount]
    effective_n: float
    local_score: Optional[float] = None
    newest_record_year: Optional[int] = None
    ves: list[VesOut]


class StatisticalModelOut(Strict):
    status: Literal["available", "not_available"]
    probability: Optional[float] = None
    cv_auc: Optional[float] = None
    n_train: Optional[int] = None
    trained_on_demo: Optional[bool] = None
    agrees: Optional[bool] = None
    text: Text


class SourceOut(Strict):
    id: str
    name: Text
    publisher: str
    layer_kind: str
    url: Optional[str] = None
    license: Optional[str] = None
    retrieved_on: Optional[str] = None
    data_last_updated: Optional[str] = None
    is_demo: bool
    notes: Optional[str] = None


class FactorInfo(Strict):
    key: str
    label: Text
    weight: float


class MethodOut(Strict):
    version: str
    name: Text
    factors: list[FactorInfo] = []      # only filled in /meta (the About page's method table)


class AnalysisResponse(Strict):
    status: Literal["ok", "insufficient_data", "out_of_coverage"]
    status_title: Optional[Text] = None
    data_mode: Literal["demo", "production"]
    is_demo: bool
    location: LocationOut
    potential: PotentialOut
    confidence: Optional[ConfidenceOut] = None
    factors: list[FactorOut]
    terrain: dict[str, Any]
    rainfall: Optional[dict[str, Any]] = None
    water_table: Optional[WaterTableOut] = None
    drilling_depth: Optional[DepthOut] = None
    local_evidence: Optional[LocalEvidenceOut] = None
    statistical_model: StatisticalModelOut
    warnings: list[Message]
    data_gaps: list[Message]
    recommendations: list[Message]
    sources: list[SourceOut]
    data_last_updated: Optional[str] = None
    method: MethodOut
    disclaimer: Text
    generated_at: str


# ----------------------------------------------------------------------------- other endpoints
class SearchItem(Strict):
    type: Literal["state", "district", "mandal", "village", "pincode"]
    id: str | int
    name: Text
    context: Text
    lat: float
    lon: float
    in_coverage: bool
    pincode: Optional[str] = None


class RegionItem(Strict):
    id: str | int
    name: Text
    lat: float
    lon: float
    in_coverage: Optional[bool] = None


class LegendItem(Strict):
    key: PotentialClass
    color: str
    label: Text
    min_score: Optional[float] = None


class MetaOut(Strict):
    app: str
    version: str
    data_mode: Literal["demo", "production"]
    state: dict[str, Any]
    languages: list[str]
    legend: list[LegendItem]
    layers: dict[str, int]
    min_zoom_for_potential_layer: int
    show_record_points: bool
    contact_email: Optional[str] = None
    ml_available: bool
    method: MethodOut
    disclaimer: Text


class DatasetsOut(Strict):
    data_mode: Literal["demo", "production"]
    sources: list[SourceOut]
    layer_counts: dict[str, int]


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=30)
    message: str = Field(min_length=5, max_length=4000)
    lang: Optional[Literal["en", "te"]] = None


class ContactOut(Strict):
    ok: bool
    id: int


class HealthOut(Strict):
    status: Literal["ok"]
    data_mode: Literal["demo", "production"]
    backend: str
