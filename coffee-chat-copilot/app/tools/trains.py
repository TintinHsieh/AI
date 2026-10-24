"""Metro-North New Haven Line lookups from data/metro_north_sample.csv."""
import csv
from datetime import date, datetime, timedelta
from functools import lru_cache

from .. import config
from .timeutil import TZ, at


@lru_cache
def _rows() -> list[dict]:
    with (config.DATA_DIR / "metro_north_sample.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def service_for(d: date) -> str:
    return {5: "saturday", 6: "sunday"}.get(d.weekday(), "weekday")


def trains_on(d: date, direction: str) -> list[dict]:
    """direction: 'to_nyc' (New Haven -> GCT) or 'to_nhv' (GCT -> New Haven)."""
    out = []
    for r in _rows():
        if r["service"] != service_for(d) or r["direction"] != direction:
            continue
        dep = at(d, r["depart"])
        if dep.hour < 3:  # after-midnight trains belong to the previous service day
            dep += timedelta(days=1)
        arr = at(dep.date(), r["arrive"])
        if arr < dep:
            arr += timedelta(days=1)
        out.append({"train": r["train"], "from": r["from"], "to": r["to"], "depart": dep, "arrive": arr})
    return sorted(out, key=lambda t: t["depart"])


def latest_arriving_by(d: date, deadline: datetime) -> dict | None:
    ok = [t for t in trains_on(d, "to_nyc") if t["arrive"] <= deadline]
    return ok[-1] if ok else None


def first_departing_after(d: date, earliest: datetime) -> dict | None:
    ok = [t for t in trains_on(d, "to_nhv") if t["depart"] >= earliest]
    return ok[0] if ok else None


def fmt(t: dict | None) -> dict | None:
    if not t:
        return None
    return {
        "train": t["train"],
        "from": t["from"],
        "to": t["to"],
        "depart": t["depart"].astimezone(TZ).strftime("%H:%M"),
        "arrive": t["arrive"].astimezone(TZ).strftime("%H:%M"),
        "minutes": int((t["arrive"] - t["depart"]).total_seconds() // 60),
    }
