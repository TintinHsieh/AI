"""Build data/metro_north_sample.csv: a SAMPLE New Haven Line timetable
(New Haven Union Station <-> Grand Central) modeled on the real service pattern.

Real schedules change. To use the real MTA timetable instead, download the
Metro-North GTFS feed and run scripts/update_timetable_from_gtfs.py.
"""
import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "metro_north_sample.csv"


def hm(m: int) -> str:
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def build():
    rows = []
    n = 1500
    for service in ("weekday", "saturday", "sunday"):
        weekday = service == "weekday"
        # New Haven -> Grand Central
        deps = []
        if weekday:
            deps += [5 * 60, 5 * 60 + 35, 6 * 60 + 5, 6 * 60 + 35, 7 * 60 + 5, 7 * 60 + 37, 8 * 60 + 7, 8 * 60 + 37]
            deps += [h * 60 + 7 for h in range(9, 24)]
        else:
            deps += [h * 60 + 22 for h in range(6, 24)]
        for d in deps:
            peak = weekday and 5 * 60 <= d <= 9 * 60
            dur = 112 if peak else 121
            rows.append([service, "to_nyc", str(n), "New Haven Union Station", hm(d), "Grand Central", hm(d + dur), "peak" if peak else "off-peak"])
            n += 1
        # Grand Central -> New Haven
        deps = []
        if weekday:
            deps += [h * 60 + 34 for h in range(6, 16)]
            deps += [16 * 60 + 7, 16 * 60 + 34, 17 * 60 + 7, 17 * 60 + 34, 18 * 60 + 7, 18 * 60 + 34, 19 * 60 + 7, 19 * 60 + 34]
            deps += [h * 60 + 34 for h in range(20, 24)] + [24 * 60 + 34]
        else:
            deps += [h * 60 + 7 for h in range(7, 25)]
        for d in deps:
            peak = weekday and 16 * 60 <= d <= 20 * 60
            dur = 115 if peak else 122
            rows.append([service, "to_nhv", str(n), "Grand Central", hm(d), "New Haven Union Station", hm(d + dur), "peak" if peak else "off-peak"])
            n += 1
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["service", "direction", "train", "from", "depart", "to", "arrive", "fare_type"])
        w.writerows(rows)
    print(f"wrote {len(rows)} trains to {OUT}")


if __name__ == "__main__":
    build()
