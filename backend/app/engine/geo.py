"""Small geodesy helpers (no GIS dependency)."""
from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_KM = 6371.0088
FT_PER_M = 3.280839895
KM_PER_DEG_LAT = 111.19492664455873      # = pi/180 * EARTH_RADIUS_KM


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Accepts scalars or numpy arrays (broadcasting)."""
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def m_to_ft(m: float) -> float:
    return float(m) * FT_PER_M


def ft_to_m(ft: float) -> float:
    return float(ft) / FT_PER_M


def bbox_around(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) that safely contains a circle of radius_km."""
    dlat = radius_km / 110.574
    dlon = radius_km / (111.320 * max(math.cos(math.radians(lat)), 0.01))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def round_to(value: float, step: float) -> float:
    return round(value / step) * step
