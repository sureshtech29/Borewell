"""Read-only API for timestamped NWIC groundwater telemetry."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..services import Container
from .common import get_container, limit_requests

router = APIRouter(prefix="/telemetry", tags=["groundwater telemetry"])


def _pool(c: Container):
    pool = getattr(c.repo, "pool", None)
    if pool is None or c.settings.backend != "postgis":
        raise HTTPException(status_code=503, detail="Groundwater telemetry requires the production PostgreSQL database")
    return pool


@router.get("/status", dependencies=[Depends(limit_requests)])
def telemetry_status(c: Container = Depends(get_container)):
    """Coverage and freshness summary for imported NWIC telemetry."""
    with _pool(c).connection() as conn:
        row = conn.execute("""
            SELECT count(DISTINCT station_code) AS stations,
                   count(*) AS observations,
                   max(observed_at) AS latest_observation,
                   max(imported_at) AS last_import
            FROM groundwater_telemetry_readings
        """).fetchone()
    return {"source": "NWIC Telangana six-hourly groundwater telemetry",
            "stations": row["stations"], "observations": row["observations"],
            "latest_observation": row["latest_observation"],
            "last_import": row["last_import"],
            "status": "no_data" if not row["observations"] else "available"}


@router.get("/stations", dependencies=[Depends(limit_requests)])
def telemetry_stations(c: Container = Depends(get_container),
                       district: str | None = Query(None, max_length=100),
                       limit: int = Query(500, ge=1, le=2000)):
    """List monitored stations with their latest available reading."""
    with _pool(c).connection() as conn:
        rows = conn.execute("""
            SELECT s.station_code, s.station_name, s.district, s.latitude, s.longitude,
                   s.agency, latest.observed_at, latest.level_value_m
            FROM groundwater_telemetry_stations s
            LEFT JOIN LATERAL (
                SELECT observed_at, level_value_m
                FROM groundwater_telemetry_readings r
                WHERE r.station_code = s.station_code
                ORDER BY observed_at DESC LIMIT 1
            ) latest ON true
            WHERE (%s IS NULL OR lower(s.district) = lower(%s))
            ORDER BY s.district, s.station_name
            LIMIT %s
        """, (district, district, limit)).fetchall()
    return {"count": len(rows), "items": rows}


@router.get("/stations/{station_code}/readings", dependencies=[Depends(limit_requests)])
def station_readings(station_code: str, c: Container = Depends(get_container),
                     limit: int = Query(200, ge=1, le=2000)):
    """Return timestamped source values for one station, newest first."""
    with _pool(c).connection() as conn:
        station = conn.execute("""
            SELECT station_code, station_name, district, latitude, longitude, agency
            FROM groundwater_telemetry_stations WHERE station_code = %s
        """, (station_code,)).fetchone()
        if station is None:
            raise HTTPException(status_code=404, detail="Monitoring station not found")
        rows = conn.execute("""
            SELECT observed_at, level_value_m, source_record_id, imported_at
            FROM groundwater_telemetry_readings
            WHERE station_code = %s ORDER BY observed_at DESC LIMIT %s
        """, (station_code, limit)).fetchall()
    return {"station": station, "count": len(rows), "items": rows}
