"""Bank office lookup + travel-time estimates inside Manhattan (no API needed)."""
import json
import math
import re
from functools import lru_cache

from .. import config

GCT = "Grand Central Terminal"
WALK_KMH = 4.8
DETOUR = 1.3          # Manhattan grid: real walking distance ~1.3x straight line
SUBWAY_KMH = 25.0
SUBWAY_OVERHEAD = 12  # walk to station + wait + walk out


@lru_cache
def offices() -> dict:
    data = json.loads((config.DATA_DIR / "bank_offices.json").read_text(encoding="utf-8"))
    data.pop("_note", None)
    return data


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9& ]", "", s.lower()).strip()


def resolve_bank(name: str | None) -> tuple[str, dict] | None:
    if not name:
        return None
    n = _norm(name)
    for canon, info in offices().items():
        if n == _norm(canon) or n in [_norm(a) for a in info.get("aliases", [])]:
            return canon, info
    for canon, info in offices().items():
        keys = [_norm(canon)] + [_norm(a) for a in info.get("aliases", []) if len(a) > 3]
        if any(k and (k in n or n in k) for k in keys):
            return canon, info
    return None


def _km(a: dict, b: dict) -> float:
    r = 6371.0
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def travel(a_name: str | None, b_name: str | None) -> dict:
    """Door-to-door minutes between two places (bank names or 'Grand Central Terminal')."""
    a = resolve_bank(a_name) or (GCT, offices()[GCT])
    b = resolve_bank(b_name) or (GCT, offices()[GCT])
    km = _km(a[1], b[1]) * DETOUR
    walk = km / WALK_KMH * 60
    if walk <= 20:
        mode, minutes = "walk", walk
    else:
        mode, minutes = "subway", SUBWAY_OVERHEAD + km / SUBWAY_KMH * 60
    return {"from": a[0], "to": b[0], "minutes": max(3, math.ceil(minutes)), "mode": mode, "km": round(km, 2)}


def office_address(name: str | None) -> str:
    r = resolve_bank(name)
    return r[1]["address"] if r else "NYC office (address not on file)"
