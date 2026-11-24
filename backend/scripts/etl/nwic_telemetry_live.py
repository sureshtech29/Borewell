"""Import timestamped Telangana NWIC telemetry into PostgreSQL.

Keeps the original numeric source value unchanged: confirm the publisher's sign
convention before interpreting it as depth below ground level.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("nwic_telemetry")
RESOURCE_ID = "ce37832e-2783-423f-90e2-ab40eaa32ed1"
API = "https://nwdp.nwic.gov.in/api/3/action/datastore_search"
IST = ZoneInfo("Asia/Kolkata")


def first(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def parse_time(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    for fmt in ("%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M",
                "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=IST)
        except ValueError:
            pass
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt


def fetch_rows(limit: int, batch_size: int = 5000):
    offset = 0
    while offset < limit:
        params = urllib.parse.urlencode({"resource_id": RESOURCE_ID,
                                         "limit": min(batch_size, limit-offset),
                                         "offset": offset})
        req = urllib.request.Request(f"{API}?{params}",
            headers={"User-Agent": "BorewellWaterFinder/1.0", "Accept": "application/json"})
        # Default TLS certificate and hostname verification remain enabled.
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("success"):
            raise RuntimeError(f"NWIC API returned success=false at offset {offset}")
        result = payload.get("result") or {}
        records = result.get("records") or []
        if not records:
            break
        for row in records:
            yield row
        offset += len(records)
        log.info("Fetched %d records", offset)
        if len(records) < min(batch_size, limit-offset+len(records)):
            break


def normalize(row):
    name = first(row, "Station", "station")
    district = first(row, "District", "district")
    lat_s, lon_s = first(row, "Latitude", "latitude"), first(row, "Longitude", "longitude")
    stamp = first(row, "Data Acquisition Time", "data acquisition time")
    value_s = first(row, "Groundwater Level Telemetry 6 Hourly (meter)",
                    "Groundwater Level Telemetry 6 Hourly (Meter)",
                    "Groundwater Level Telemetry 6 Hourly (meter) ")
    if not (name and lat_s and lon_s and stamp and value_s):
        return None
    lat, lon, value = float(lat_s), float(lon_s), float(value_s)
    if not (15.8 <= lat <= 19.9 and 77.0 <= lon <= 81.8):
        return None
    if not (-500 <= value <= 500):
        return None
    observed = parse_time(stamp)
    # Prefer a publisher station identifier. Fallback is stable across identical
    # name/district/coordinate records, but may need reconciliation with official IDs.
    official_id = first(row, "SlNo", "Station ID", "Station Code", "station_id")
    fallback = re.sub(r"[^A-Z0-9]+", "_", f"{district}_{name}_{lat:.5f}_{lon:.5f}".upper()).strip("_")
    code = official_id or fallback
    return {
        "station_code": code, "station_name": name, "district": district or None,
        "latitude": lat, "longitude": lon,
        "agency": first(row, "Agency") or "Telangana State Ground Water Department",
        "observed_at": observed, "level_value_m": value,
        "source_record_id": first(row, "_id", "id") or None,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required (use Render Internal Database URL)")
    records = []
    for attempt in range(args.retries):
        try:
            records = [item for raw in fetch_rows(args.limit) if (item := normalize(raw))]
            break
        except Exception:
            if attempt + 1 == args.retries:
                raise
            log.exception("NWIC fetch failed; retrying")
            time.sleep(2 ** attempt)
    if not records:
        raise SystemExit("No valid NWIC records fetched; database was not modified")
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO groundwater_telemetry_stations
                    (station_code, station_name, district, latitude, longitude, agency)
                VALUES (%(station_code)s, %(station_name)s, %(district)s,
                        %(latitude)s, %(longitude)s, %(agency)s)
                ON CONFLICT (station_code) DO UPDATE SET
                    station_name=EXCLUDED.station_name, district=EXCLUDED.district,
                    latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude,
                    agency=EXCLUDED.agency, updated_at=now()
            """, records)
            cur.executemany("""
                INSERT INTO groundwater_telemetry_readings
                    (station_code, observed_at, level_value_m, source_record_id)
                VALUES (%(station_code)s, %(observed_at)s, %(level_value_m)s, %(source_record_id)s)
                ON CONFLICT (station_code, observed_at) DO UPDATE SET
                    level_value_m=EXCLUDED.level_value_m,
                    source_record_id=EXCLUDED.source_record_id, imported_at=now()
            """, records)
    log.info("Imported %d valid timestamped observations from NWIC", len(records))


if __name__ == "__main__":
    main()
