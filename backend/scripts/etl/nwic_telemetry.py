"""ETL pipeline for NWDP / NWIC Telangana Groundwater Level Telemetry Data.

Source: National Water Data Portal (NWIC) & Telangana State Ground Water Department
Dataset: Ground Water Level Telemetry Six Hourly Telangana (2026 - 2030)
Portal URL: https://nwdp.nwic.gov.in/dataset/ground-water-level-telemetry-daily-telangana-gw/resource/ce37832e-2783-423f-90e2-ab40eaa32ed1
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nwic_etl")

RESOURCE_URL = "https://nwdp.nwic.gov.in/dataset/ground-water-level-telemetry-daily-telangana-gw/resource/ce37832e-2783-423f-90e2-ab40eaa32ed1"
DOWNLOAD_URL = "https://nwdp.nwic.gov.in/dataset/6a154d99-e0d6-426f-920e-96f116ef567e/resource/ce37832e-2783-423f-90e2-ab40eaa32ed1/download/gwl_tel_6_hourly_telangana_gw_ts_2026_2030.csv"
API_URL = "https://nwdp.nwic.gov.in/api/3/action/datastore_search?resource_id=ce37832e-2783-423f-90e2-ab40eaa32ed1"

# Telangana approx geographic boundaries
LAT_MIN, LAT_MAX = 15.8, 19.9
LON_MIN, LON_MAX = 77.0, 81.8


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.strip()).strip()
    return re.sub(r"[-\s]+", "_", text).upper()


def get_season(dt: datetime) -> str:
    month = dt.month
    if month in (3, 4, 5):
        return "pre_monsoon"
    elif month in (6, 7, 8, 9):
        return "monsoon"
    elif month in (10, 11):
        return "post_monsoon"
    else:
        return "winter"


def parse_telemetry_row(row: dict) -> Optional[Tuple[str, dict, dict]]:
    station_name = (row.get("Station") or row.get("station") or "").strip()
    district = (row.get("District") or row.get("district") or "").strip()
    lat_str = (row.get("Latitude") or row.get("latitude") or "").strip()
    lon_str = (row.get("Longitude") or row.get("longitude") or "").strip()
    dt_str = (row.get("Data Acquisition Time") or row.get("data acquisition time") or "").strip()
    val_str = (row.get("Groundwater Level Telemetry 6 Hourly (meter)") or "").strip()

    if not station_name or not lat_str or not lon_str or not dt_str:
        return None

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return None

    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None

    # Parse groundwater level: NWIC reports negative values for depth below ground level
    try:
        val = abs(float(val_str)) if val_str else None
        if val is None or val > 200.0 or val <= 0:
            return None
    except ValueError:
        return None

    # Parse date (format: DD-MM-YYYY HH:MM or YYYY-MM-DD)
    parsed_date = None
    for fmt in ("%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed_date = datetime.strptime(dt_str, fmt)
            break
        except ValueError:
            pass

    if not parsed_date:
        return None

    code = f"{slugify(district)}_{slugify(station_name)}" if district and district != "-" else slugify(station_name)
    display_name = f"{station_name} ({district})" if district and district != "-" else station_name

    station_info = {
        "station_code": code,
        "name": display_name,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "agency": (row.get("Agency") or "Telangana GW").strip(),
        "well_type": "piezometer",
        "district": district,
    }

    reading_info = {
        "station_code": code,
        "date": parsed_date.strftime("%Y-%m-%d"),
        "depth_to_water_m": round(val, 2),
        "season": get_season(parsed_date),
    }

    return code, station_info, reading_info


def fetch_from_api(limit: int = 50000) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Fetch telemetry records using the NWDP CKAN datastore API."""
    log.info("Fetching telemetry data from NWDP CKAN API (limit: %d)...", limit)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    stations: Dict[str, dict] = {}
    readings: Dict[str, dict] = {}  # key: (code, date) -> reading

    offset = 0
    batch_size = 5000

    while offset < limit:
        url = f"{API_URL}&limit={batch_size}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        try:
            with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning("API fetch error at offset %d: %s", offset, e)
            break

        records = data.get("result", {}).get("records", [])
        if not records:
            break

        for r in records:
            res = parse_telemetry_row(r)
            if not res:
                continue
            code, s_info, rd_info = res
            stations.setdefault(code, s_info)
            rd_key = f"{code}_{rd_info['date']}"
            readings[rd_key] = rd_info

        offset += len(records)
        log.info("Processed %d API records (%d stations, %d readings)...", offset, len(stations), len(readings))

    return stations, readings


def process_csv_stream(stream, max_rows: Optional[int] = None) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    reader = csv.DictReader(stream)
    stations: Dict[str, dict] = {}
    readings: Dict[str, dict] = {}
    count = 0

    for row in reader:
        count += 1
        res = parse_telemetry_row(row)
        if not res:
            continue
        code, s_info, rd_info = res
        stations.setdefault(code, s_info)
        rd_key = f"{code}_{rd_info['date']}"
        readings[rd_key] = rd_info

        if max_rows and count >= max_rows:
            break

    return stations, readings


def save_outputs(stations: Dict[str, dict], readings: Dict[str, dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. stations.csv (matches scripts.etl.load wells schema)
    stations_path = output_dir / "stations.csv"
    with open(stations_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["station_code", "name", "lat", "lon", "agency", "well_type"])
        writer.writeheader()
        for s in stations.values():
            writer.writerow({
                "station_code": s["station_code"],
                "name": s["name"],
                "lat": s["lat"],
                "lon": s["lon"],
                "agency": s["agency"],
                "well_type": s["well_type"],
            })
    log.info("Saved %d stations to %s", len(stations), stations_path)

    # 2. readings.csv
    readings_path = output_dir / "readings.csv"
    with open(readings_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["station_code", "date", "depth_to_water_m", "season"])
        writer.writeheader()
        for r in readings.values():
            writer.writerow(r)
    log.info("Saved %d readings to %s", len(readings), readings_path)

    # 3. JSON format for in-memory backend
    wells_json = []
    rd_by_station: Dict[str, list] = {}
    for r in readings.values():
        rd_by_station.setdefault(r["station_code"], []).append({
            "date": r["date"],
            "depth_to_water_m": r["depth_to_water_m"],
            "season": r["season"],
        })

    for idx, (code, s) in enumerate(stations.items(), start=1):
        wells_json.append({
            "well_id": idx,
            "station_code": code,
            "name": s["name"],
            "lat": s["lat"],
            "lon": s["lon"],
            "agency": s["agency"],
            "readings": sorted(rd_by_station.get(code, []), key=lambda x: x["date"]),
        })

    json_path = output_dir / "telangana_nwic_wells.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(wells_json, f, indent=2)
    log.info("Saved in-memory wells JSON to %s", json_path)


def main():
    parser = argparse.ArgumentParser(description="Fetch and process NWDP Telangana Groundwater Telemetry data.")
    parser.add_argument("--file", type=str, help="Path to locally downloaded CSV file (optional).")
    parser.add_argument("--api-limit", type=int, default=30000, help="Max records to fetch from API if downloading.")
    parser.add_argument("--out-dir", type=str, default="data", help="Output directory for generated CSV/JSON files.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    if args.file and Path(args.file).exists():
        log.info("Processing local file: %s", args.file)
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            stations, readings = process_csv_stream(f)
    else:
        log.info("Fetching telemetry data directly from NWDP API (%s)...", RESOURCE_URL)
        stations, readings = fetch_from_api(limit=args.api_limit)

    save_outputs(stations, readings, out_dir)
    print("\n[SUCCESS] Telemetry data processed successfully!")
    print(f"Stations: {len(stations)}")
    print(f"Readings: {len(readings)}")
    print(f"Files written to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
