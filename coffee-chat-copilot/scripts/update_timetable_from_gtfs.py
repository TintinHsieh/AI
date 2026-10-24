"""Replace the sample timetable with the REAL Metro-North schedule.

1. Download the Metro-North GTFS zip from the MTA developer site
   (https://new.mta.info/developers -> Metro-North Railroad GTFS).
2. python scripts/update_timetable_from_gtfs.py path/to/google_transit.zip

Writes data/metro_north_sample.csv in the same format the app reads.
Trips are grouped by service days (weekday / saturday / sunday) using calendar.txt.
"""
import csv
import io
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "metro_north_sample.csv"


def read(z, name):
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def norm_time(t):
    h, m, *_ = t.split(":")
    return f"{int(h) % 24:02d}:{int(m):02d}"


def main(path):
    z = zipfile.ZipFile(path)
    stops = read(z, "stops.txt")
    nhv = {s["stop_id"] for s in stops if s["stop_name"].strip().lower() == "new haven"}
    gct = {s["stop_id"] for s in stops if "grand central" in s["stop_name"].lower()}
    if not nhv or not gct:
        sys.exit("Could not find New Haven / Grand Central in stops.txt")
    service_kind = {}
    for c in read(z, "calendar.txt") if "calendar.txt" in z.namelist() else []:
        if any(c[d] == "1" for d in ("monday", "tuesday", "wednesday", "thursday", "friday")):
            service_kind[c["service_id"]] = "weekday"
        elif c["saturday"] == "1":
            service_kind[c["service_id"]] = "saturday"
        elif c["sunday"] == "1":
            service_kind[c["service_id"]] = "sunday"
    trips = {t["trip_id"]: t for t in read(z, "trips.txt")}
    by_trip = {}
    for st in read(z, "stop_times.txt"):
        if st["stop_id"] in nhv or st["stop_id"] in gct:
            by_trip.setdefault(st["trip_id"], []).append(st)
    rows, seen = [], set()
    for trip_id, sts in by_trip.items():
        a = [s for s in sts if s["stop_id"] in nhv]
        b = [s for s in sts if s["stop_id"] in gct]
        if not a or not b:
            continue
        a, b = a[0], b[0]
        kind = service_kind.get(trips.get(trip_id, {}).get("service_id"))
        if not kind:
            continue
        if int(a["stop_sequence"]) < int(b["stop_sequence"]):
            row = (kind, "to_nyc", trips[trip_id].get("trip_short_name", trip_id), "New Haven Union Station",
                   norm_time(a["departure_time"]), "Grand Central", norm_time(b["arrival_time"]), "")
        else:
            row = (kind, "to_nhv", trips[trip_id].get("trip_short_name", trip_id), "Grand Central",
                   norm_time(b["departure_time"]), "New Haven Union Station", norm_time(a["arrival_time"]), "")
        key = (row[0], row[1], row[4])
        if key not in seen:
            seen.add(key)
            rows.append(row)
    rows.sort(key=lambda r: (r[0], r[1], r[4]))
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["service", "direction", "train", "from", "depart", "to", "arrive", "fare_type"])
        w.writerows(rows)
    print(f"wrote {len(rows)} real trains to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
