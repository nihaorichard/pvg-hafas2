#!/usr/bin/env python3
"""
Downloads the VMT (Verkehrsverbund Mittelthueringen) GTFS static feed and
extracts a small JSON file containing every scheduled departure at the
configured stop(s), plus the service-calendar info needed to work out which
trips run on any given date.

This script only touches GTFS *static* data (there is no public VMT
GTFS-Realtime feed at the time of writing), so the dashboard shows the
timetable, not live delays.

Run with: python3 scripts/build_data.py
Reads config from stop_config.json (same folder).
Writes docs/data.json.
"""
import csv
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(HERE, "stop_config.json")
OUT_PATH = os.path.join(ROOT, "docs", "data.json")

GTFS_URL = "https://www.vmt-thueringen.de/fileadmin/VMT_Redaktion/OPEN_DATA/VMT_GTFS.zip"


def log(*args):
    print(*args, file=sys.stderr)


def download_zip(url: str) -> zipfile.ZipFile:
    log(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "vmt-dashboard-build/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    log(f"Downloaded {len(data) / 1_000_000:.1f} MB")
    return zipfile.ZipFile(io.BytesIO(data))


def read_csv_from_zip(zf: zipfile.ZipFile, name: str):
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        reader = csv.DictReader(text)
        for row in reader:
            yield row


def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    stop_ids = set(config["stop_ids"].keys())
    if not stop_ids:
        log("No stop_ids configured in stop_config.json - aborting.")
        sys.exit(1)

    zf = download_zip(GTFS_URL)
    names = set(zf.namelist())
    log("Feed contains:", sorted(names))

    feed_info = {}
    if "feed_info.txt" in names:
        for row in read_csv_from_zip(zf, "feed_info.txt"):
            feed_info = row
            break

    stops = {}
    for row in read_csv_from_zip(zf, "stops.txt"):
        if row["stop_id"] in stop_ids:
            stops[row["stop_id"]] = {
                "stop_id": row["stop_id"],
                "stop_name": row.get("stop_name", ""),
                "stop_lat": row.get("stop_lat", ""),
                "stop_lon": row.get("stop_lon", ""),
            }
    missing = stop_ids - stops.keys()
    if missing:
        log(f"WARNING: these stop_ids were not found in stops.txt: {missing}")

    routes = {}
    for row in read_csv_from_zip(zf, "routes.txt"):
        routes[row["route_id"]] = {
            "route_short_name": row.get("route_short_name", ""),
            "route_long_name": row.get("route_long_name", ""),
            "route_color": row.get("route_color", ""),
            "route_type": row.get("route_type", ""),
        }

    calendars = {}
    if "calendar.txt" in names:
        for row in read_csv_from_zip(zf, "calendar.txt"):
            calendars[row["service_id"]] = {
                "monday": int(row.get("monday", 0) or 0),
                "tuesday": int(row.get("tuesday", 0) or 0),
                "wednesday": int(row.get("wednesday", 0) or 0),
                "thursday": int(row.get("thursday", 0) or 0),
                "friday": int(row.get("friday", 0) or 0),
                "saturday": int(row.get("saturday", 0) or 0),
                "sunday": int(row.get("sunday", 0) or 0),
                "start_date": row.get("start_date", ""),
                "end_date": row.get("end_date", ""),
            }

    calendar_exceptions = {}
    if "calendar_dates.txt" in names:
        for row in read_csv_from_zip(zf, "calendar_dates.txt"):
            sid = row["service_id"]
            calendar_exceptions.setdefault(sid, []).append(
                {"date": row["date"], "exception_type": int(row["exception_type"])}
            )

    log("Reading trips.txt ...")
    trips = {}
    for row in read_csv_from_zip(zf, "trips.txt"):
        trips[row["trip_id"]] = {
            "route_id": row.get("route_id", ""),
            "service_id": row.get("service_id", ""),
            "trip_headsign": row.get("trip_headsign", ""),
            "direction_id": row.get("direction_id", ""),
        }

    log("Scanning stop_times.txt (this file is large, please wait) ...")
    departures = []
    count = 0
    for row in read_csv_from_zip(zf, "stop_times.txt"):
        count += 1
        if count % 2_000_000 == 0:
            log(f"  ...{count:,} rows scanned")
        sid = row["stop_id"]
        if sid not in stop_ids:
            continue
        trip = trips.get(row["trip_id"])
        if not trip:
            continue
        route = routes.get(trip["route_id"], {})
        departures.append(
            {
                "stop_id": sid,
                "trip_id": row["trip_id"],
                "departure_time": row.get("departure_time") or row.get("arrival_time") or "",
                "service_id": trip["service_id"],
                "route_short_name": route.get("route_short_name", ""),
                "route_long_name": route.get("route_long_name", ""),
                "route_color": route.get("route_color", ""),
                "trip_headsign": trip["trip_headsign"],
                "direction_id": trip["direction_id"],
            }
        )
    log(f"Scanned {count:,} stop_times rows, kept {len(departures):,} for our stop(s).")

    used_service_ids = {d["service_id"] for d in departures}
    calendars = {k: v for k, v in calendars.items() if k in used_service_ids}
    calendar_exceptions = {k: v for k, v in calendar_exceptions.items() if k in used_service_ids}

    departures.sort(key=lambda d: (d["stop_id"], d["departure_time"]))

    from collections import Counter

    headsign_counts = {sid: Counter() for sid in stop_ids}
    for d in departures:
        if d["trip_headsign"]:
            headsign_counts[d["stop_id"]][d["trip_headsign"]] += 1
    auto_labels = {
        sid: (counter.most_common(1)[0][0] if counter else config["stop_ids"].get(sid, sid))
        for sid, counter in headsign_counts.items()
    }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": GTFS_URL,
        "feed_info": feed_info,
        "stop_group_name": config.get("stop_group_name", ""),
        "stop_labels": config["stop_ids"],
        "auto_direction_labels": auto_labels,
        "stops": stops,
        "calendars": calendars,
        "calendar_exceptions": calendar_exceptions,
        "departures": departures,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) / 1024
    log(f"Wrote {OUT_PATH} ({size_kb:.1f} KB) with {len(departures):,} departures.")


if __name__ == "__main__":
    main()
