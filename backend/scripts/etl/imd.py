"""Reader for the IMD 0.25 deg gridded daily rainfall binary (.GRD).

Layout (IMD Pune, 'Rainfall_ind<year>_rfp25.grd'): float32, little-endian, one 2-D field per day,
129 latitude rows (6.5N..38.5N, south first) x 135 longitude columns (66.5E..100.0E), undefined = -999.
The layout is verified from the file size (days x 129 x 135 x 4 bytes); a size that fits neither 365 nor 366 days is rejected.
"""
from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np

NLAT, NLON = 129, 135
LAT0, LON0, STEP = 6.5, 66.5, 0.25
UNDEF = -999.0


def grid_coords():
    lats = LAT0 + STEP * np.arange(NLAT)
    lons = LON0 + STEP * np.arange(NLON)
    return lats, lons


def read_grd(path: str | Path, year: int) -> np.ndarray:
    """-> array (ndays, 129, 135) with NaN for undefined."""
    size = Path(path).stat().st_size
    days = 366 if calendar.isleap(year) else 365
    expected = days * NLAT * NLON * 4
    if size != expected:
        raise ValueError(f"{path}: {size} bytes, expected {expected} for {days} days of a {NLAT}x{NLON} float32 grid "
                         f"({year}). Wrong year, or not an IMD 0.25 deg rainfall file.")
    a = np.fromfile(path, dtype="<f4").reshape(days, NLAT, NLON).astype("float32")
    a[(a <= UNDEF + 1) | (a < 0)] = np.nan
    return a


def annual_totals(a: np.ndarray, year: int, max_missing_days: int = 5):
    """-> (annual_mm, monsoon_mm) each (129,135); cells with more than `max_missing_days` undefined days are NaN."""
    missing = np.isnan(a).sum(axis=0)
    ann = np.nansum(a, axis=0)
    jun1 = (np.datetime64(f"{year}-06-01") - np.datetime64(f"{year}-01-01")).astype(int)
    oct1 = (np.datetime64(f"{year}-10-01") - np.datetime64(f"{year}-01-01")).astype(int)
    mon = np.nansum(a[jun1:oct1], axis=0)
    bad = missing > max_missing_days
    ann[bad] = np.nan
    mon[bad] = np.nan
    return ann, mon


def cell_key(lon: float, lat: float) -> str:
    return f"imd025_{lon:.2f}_{lat:.2f}"
