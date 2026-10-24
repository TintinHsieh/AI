"""NYC day itinerary (deterministic, zero tokens)."""
from datetime import date, timedelta

from . import calendar as cal
from .timeutil import at, clock, now, overlaps, parse_dt

MEALS = [("lunch", "11:30", "14:00"), ("dinner", "17:30", "21:00")]


def day_plan(profile: dict, holds: list[dict], d: date, include_held: bool = True) -> dict:
    statuses = ("confirmed", "held") if include_held else ("confirmed",)
    chats = [h for h in holds if h["status"] in statuses and parse_dt(h["start"]).date() == d]
    in_person = [h for h in chats if h["mode"] == "in_person"]
    virtual = [h for h in chats if h["mode"] != "in_person"]
    out = {"date": d.isoformat(), "chats": chats, "steps": [], "meals": [], "flags": [], "trip": None}
    if not in_person:
        return out
    # when several holds from the same banker fall on this day, plan with the earliest one
    seen, use = set(), []
    for h in sorted(in_person, key=lambda h: (h["status"] != "confirmed", h["start"])):
        if h["thread_id"] not in seen:
            seen.add(h["thread_id"])
            use.append(h)
    plan = cal.plan_trip(profile, d, [{"start": parse_dt(h["start"]), "end": parse_dt(h["end"]), "bank": h.get("bank"),
                                        "label": h.get("label")} for h in use])
    if "error" in plan:
        out["flags"].append({"level": "bad", "text": "This day doesn't work as planned: " + plan["error"]})
        return out
    out["trip"] = {"leave": clock(plan["leave"]), "home": clock(plan["home"])}
    out["steps"] = [{"time": clock(s["time"]), "type": s["type"], "text": s["text"],
                     "end": clock(s["end"]) if s.get("end") else None} for s in plan["steps"]]
    # free gaps in NYC between steps -> meal / treat windows
    busy = []
    for s in plan["steps"]:
        if s["type"] == "chat":
            busy.append((s["time"], s["end"]))
    ot, rt = plan["out_train"], plan["return_train"]
    busy += [(ot["depart"], ot["arrive"]), (rt["depart"], rt["arrive"])]
    for name, a, b in MEALS:
        w0, w1 = at(d, a), at(d, b)
        if not overlaps(plan["leave"], plan["home"], w0, w1):
            continue
        t, found = max(w0, ot["arrive"]), None
        while t + timedelta(minutes=40) <= min(w1, rt["depart"]):
            if not any(overlaps(t, t + timedelta(minutes=40), s0 - timedelta(minutes=15), s1 + timedelta(minutes=10)) for s0, s1 in busy):
                found = t
                break
            t += timedelta(minutes=15)
        if found:
            out["meals"].append({"meal": name, "time": clock(found), "text": f"{clock(found)}: 40 min free for a real {name}. Book it like a meeting."})
        elif any(overlaps(t0, t1, w0, w1) for t0, t1 in [(ot["depart"], ot["arrive"]), (rt["depart"], rt["arrive"])]):
            out["meals"].append({"meal": name, "time": None, "text": f"No sit-down {name} window. Grab food at Grand Central and eat on the train."})
        else:
            out["flags"].append({"level": "warn", "text": f"No {name} window. Pack a snack."})
    if plan["home"].hour >= 22 or plan["home"].date() > d:
        out["flags"].append({"level": "warn", "text": f"Late night: back on campus around {clock(plan['home'])}. Keep tomorrow morning light."})
    if plan["leave"].hour < 7:
        out["flags"].append({"level": "warn", "text": f"Early start: leave campus at {clock(plan['leave'])}. Lay out your suit the night before."})
    if virtual:
        out["flags"].append({"level": "info", "text": f"{len(virtual)} virtual chat(s) also on this day."})
    return out


def best_nyc_day(holds: list[dict], days: list[str]) -> str | None:
    """Default view: the day with the most confirmed in-person chats, then the most chats overall."""
    def score(d):
        hs = [h for h in holds if h["status"] in ("held", "confirmed") and h["mode"] == "in_person" and h["start"][:10] == d]
        return (sum(h["status"] == "confirmed" for h in hs), len({h["thread_id"] for h in hs}))
    return max(days, key=score) if days else None


def upcoming_nyc_days(profile: dict, holds: list[dict], days: int = 21) -> list[str]:
    t = now()
    ds = sorted({parse_dt(h["start"]).date() for h in holds
                 if h["status"] in ("held", "confirmed") and h["mode"] == "in_person" and parse_dt(h["start"]) >= t - timedelta(hours=12)})
    return [d.isoformat() for d in ds if (d - t.date()).days <= days]
