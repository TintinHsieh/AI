"""Free/busy logic: classes, holds, confirmed chats, NYC trip feasibility.

All of this is deterministic Python so the LLM can never invent a free time
or a train. Agents only see generic reasons ("conflicts with a class"), never
class names, so nothing private can leak into a reply to a banker.
"""
from datetime import date, datetime, timedelta

from . import nyc, trains
from .timeutil import DAY_NAMES, at, daterange, iso, now, overlaps, parse_dt, parse_hm, pretty, clock

ACTIVE = ("held", "confirmed")


# ---------------------------------------------------------------- busy blocks
def fixed_busy(profile: dict, d: date) -> list[dict]:
    out = []
    day = DAY_NAMES[d.weekday()]
    for c in profile.get("classes", []):
        if day in c.get("days", []):
            out.append({"start": at(d, c["start"]), "end": at(d, c["end"]), "kind": "class", "label": c["name"]})
    for c in profile.get("commitments", []):
        if c.get("date") == d.isoformat() or day in c.get("days", []):
            out.append({"start": at(d, c["start"]), "end": at(d, c["end"]), "kind": "commitment", "label": c["name"]})
    return out


def refresh_holds(holds: list[dict], t: datetime | None = None) -> list[dict]:
    t = t or now()
    for h in holds:
        if h["status"] == "held" and h.get("expires_at") and parse_dt(h["expires_at"]) < t:
            h["status"] = "expired"
    return holds


def chats_on(holds: list[dict], d: date, exclude_thread: str | None = None) -> list[dict]:
    out = []
    for h in holds:
        if h["status"] in ACTIVE and h.get("thread_id") != exclude_thread:
            s = parse_dt(h["start"])
            if s.date() == d:
                out.append({**h, "_start": s, "_end": parse_dt(h["end"])})
    return sorted(out, key=lambda h: h["_start"])


# ---------------------------------------------------------------- NYC trips
def plan_trip(profile: dict, d: date, chats: list[dict]) -> dict:
    """chats: [{start: dt, end: dt, bank: str, label: str}] in-person, same day."""
    if not chats:
        return {"error": "no in-person chats"}
    chats = sorted(chats, key=lambda c: c["start"])
    steps = []
    first = chats[0]
    leg = nyc.travel(nyc.GCT, first["bank"])
    deadline = first["start"] - timedelta(minutes=profile["arrive_early_min"] + leg["minutes"])
    out_train = trains.latest_arriving_by(d, deadline)
    if not out_train:
        return {"error": "no Metro-North train reaches Grand Central early enough"}
    leave = out_train["depart"] - timedelta(minutes=profile["campus_to_station_min"])
    steps.append({"time": leave, "type": "leave", "text": f"Leave campus for {profile['home_station']}"})
    steps.append({"time": out_train["depart"], "type": "train", "text": f"Metro-North #{out_train['train']} to Grand Central (arrives {clock(out_train['arrive'])})"})
    steps.append({"time": out_train["arrive"], "type": "travel", "text": f"{leg['mode'].title()} {leg['minutes']} min to {leg['to']} ({nyc.office_address(first['bank'])})"})
    for i, c in enumerate(chats):
        if i > 0:
            prev = chats[i - 1]
            leg = nyc.travel(prev["bank"], c["bank"])
            need = max(leg["minutes"] + 10, profile.get("between_chats_buffer_min", 20))
            gap = (c["start"] - prev["end"]).total_seconds() / 60
            if gap < need:
                return {"error": f"only {int(gap)} min between chats, need {need} to get from {leg['from']} to {leg['to']}"}
            steps.append({"time": prev["end"], "type": "travel", "text": f"{leg['mode'].title()} {leg['minutes']} min to {leg['to']} ({nyc.office_address(c['bank'])})"})
        steps.append({"time": c["start"], "type": "chat", "text": c.get("label") or f"Coffee chat at {c['bank']}", "end": c["end"]})
    last = chats[-1]
    leg = nyc.travel(last["bank"], nyc.GCT)
    ret = trains.first_departing_after(d, last["end"] + timedelta(minutes=leg["minutes"] + 5))
    if not ret:
        return {"error": "no train back to New Haven after the last chat"}
    steps.append({"time": last["end"], "type": "travel", "text": f"{leg['mode'].title()} {leg['minutes']} min back to Grand Central"})
    steps.append({"time": ret["depart"], "type": "train", "text": f"Metro-North #{ret['train']} to New Haven (arrives {clock(ret['arrive'])})"})
    home = ret["arrive"] + timedelta(minutes=profile["station_to_campus_min"])
    steps.append({"time": home, "type": "home", "text": "Back on campus"})
    return {"leave": leave, "home": home, "out_train": out_train, "return_train": ret, "steps": steps}


def _in_person(chats: list[dict]) -> list[dict]:
    return [{"start": c["_start"], "end": c["_end"], "bank": c.get("bank"), "label": c.get("label")} for c in chats if c.get("mode") == "in_person"]


# ---------------------------------------------------------------- slot checks
def check_slot(profile: dict, holds: list[dict], start: datetime, mode: str, bank: str | None,
               thread_id: str | None = None, t_now: datetime | None = None) -> dict:
    t_now = t_now or now()
    block = timedelta(minutes=profile["chat_block_min"])
    end = start + block
    d = start.date()
    reasons = []
    if start < t_now + timedelta(hours=3):
        reasons.append("too soon (less than 3 hours from now)")
    if start.time() < parse_hm(profile["earliest_chat"]) or end.time() > parse_hm(profile["latest_chat_end"]) or end.date() != d:
        reasons.append("outside your preferred chat hours")
    busy = fixed_busy(profile, d)
    others = chats_on(holds, d, exclude_thread=thread_id)
    wb = profile.get("wellbeing", {})
    if len({c.get("thread_id") for c in others}) >= wb.get("max_chats_per_day", 99):
        reasons.append("day already at your wellbeing limit for chats")
    result = {"ok": False, "start": start, "end": end, "mode": mode, "bank": bank}
    if mode == "in_person":
        trip_chats = _in_person(others) + [{"start": start, "end": end, "bank": bank, "label": "this chat"}]
        plan = plan_trip(profile, d, trip_chats)
        if "error" in plan:
            reasons.append(plan["error"])
        else:
            result["plan"] = plan
            for b in busy:
                if overlaps(plan["leave"], plan["home"], b["start"], b["end"]):
                    reasons.append(f"NYC trip overlaps a {b['kind']}")
                    break
            for c in others:
                if c.get("mode") != "in_person" and overlaps(plan["leave"], plan["home"], c["_start"], c["_end"]):
                    reasons.append("NYC trip overlaps another (virtual) chat")
                    break
    else:
        buf = timedelta(minutes=profile.get("virtual_buffer_min", 10))
        for b in busy:
            if overlaps(start - buf, end + buf, b["start"], b["end"]):
                reasons.append(f"conflicts with a {b['kind']}")
                break
        for c in others:
            if overlaps(start - buf, end + buf, c["_start"], c["_end"]):
                reasons.append("overlaps another coffee chat or hold")
                break
        ip = _in_person(others)
        if ip:
            plan = plan_trip(profile, d, ip)
            if "error" not in plan and overlaps(start, end, plan["leave"], plan["home"]):
                reasons.append("you will be traveling to/in NYC then")
    if mode == "in_person":
        for c in others:
            if overlaps(start, end, c["_start"], c["_end"]):
                reasons.append("overlaps another coffee chat or hold")
                break
    result["ok"] = not reasons
    result["reasons"] = sorted(set(reasons), key=reasons.index)
    return result


def slot_public(r: dict) -> dict:
    """What agents / the UI see for a slot (no class names)."""
    out = {"start": iso(r["start"]), "end": iso(r["end"]), "label": f"{pretty(r['start'])} - {clock(r['end'])} ET",
           "mode": r["mode"], "ok": r["ok"], "reasons": r.get("reasons", [])}
    if r.get("bank"):
        out["bank"] = r["bank"]
    p = r.get("plan")
    if p and r["mode"] == "in_person":
        out["trip"] = {
            "leave_campus": clock(p["leave"]),
            "train_out": trains.fmt(p["out_train"]),
            "train_back": trains.fmt(p["return_train"]),
            "back_on_campus": clock(p["home"]),
        }
    return out


def find_open_slots(profile: dict, holds: list[dict], start_date: date, end_date: date, mode: str,
                    bank: str | None = None, thread_id: str | None = None, earliest: str | None = None,
                    latest: str | None = None, weekdays: list[str] | None = None, limit: int = 8,
                    t_now: datetime | None = None) -> list[dict]:
    t_now = t_now or now()
    start_date = max(start_date, t_now.date() + timedelta(days=1))  # never offer same-day times
    end_date = min(end_date, start_date + timedelta(days=21))
    block = profile["chat_block_min"]
    lo = max(parse_hm(profile["earliest_chat"]), parse_hm(earliest)) if earliest else parse_hm(profile["earliest_chat"])
    hi = min(parse_hm(profile["latest_chat_end"]), parse_hm(latest)) if latest else parse_hm(profile["latest_chat_end"])
    cands = []
    for d in daterange(start_date, end_date):
        if weekdays and DAY_NAMES[d.weekday()] not in weekdays:
            continue
        if DAY_NAMES[d.weekday()] not in profile.get("chat_days", DAY_NAMES[:5]):
            continue
        has_class = bool([b for b in fixed_busy(profile, d) if b["kind"] == "class"])
        others = chats_on(holds, d, exclude_thread=thread_id)
        nyc_day = any(c.get("mode") == "in_person" for c in others)
        s = at(d, lo)
        while (s + timedelta(minutes=block)).time() <= hi and (s + timedelta(minutes=block)).date() == d:
            r = check_slot(profile, holds, s, mode, bank, thread_id, t_now)
            if r["ok"]:
                score = -0.6 * len(others)
                if mode == "in_person":
                    score += (3 if nyc_day else 0) + (2 if not has_class else 0) + (1 if 9 <= s.hour and s.hour + 1.5 <= 17 else 0)
                    score -= ((r["plan"]["home"] - r["plan"]["leave"]).total_seconds() / 3600) * 0.3
                else:
                    score += (1 if not has_class else 0) + (0.5 if 10 <= s.hour <= 16 else 0)
                score -= (d - start_date).days * 0.05
                cands.append((score, s, r))
            s += timedelta(minutes=30)
    cands.sort(key=lambda x: (-x[0], x[1]))
    picked, per_day = [], {}
    for score, s, r in cands:
        d = s.date()
        if per_day.get(d, 0) >= 2:
            continue
        if any(p[1].date() == d and abs((p[1] - s).total_seconds()) < block * 60 * 1.5 for p in picked):
            continue
        picked.append((score, s, r))
        per_day[d] = per_day.get(d, 0) + 1
        if len(picked) >= limit:
            break
    picked.sort(key=lambda x: x[1])
    return [{**slot_public(r), "score": round(sc, 2)} for sc, _, r in picked]


# ---------------------------------------------------------------- holds
def place_holds(holds: list[dict], thread: dict, slots: list[dict], profile: dict) -> list[dict]:
    for h in holds:
        if h.get("thread_id") == thread["id"] and h["status"] == "held":
            h["status"] = "released"
    t = now()
    new = []
    for s in slots:
        new.append({
            "id": f"hold_{thread['id'][-6:]}_{len(holds) + len(new)}",
            "thread_id": thread["id"],
            "banker": thread.get("banker_name"),
            "bank": s.get("bank") or thread.get("bank"),
            "mode": s["mode"],
            "start": s["start"],
            "end": s["end"],
            "status": "held",
            "created_at": iso(t),
            "expires_at": iso(t + timedelta(hours=profile.get("hold_expiry_hours", 48))),
            "label": f"Coffee chat - {thread.get('banker_name') or 'banker'} ({thread.get('bank') or 'bank'})",
        })
    holds.extend(new)
    return new


def confirm_hold(holds: list[dict], hold_id: str) -> dict | None:
    target = next((h for h in holds if h["id"] == hold_id), None)
    if not target:
        return None
    for h in holds:
        if h.get("thread_id") == target["thread_id"] and h["status"] in ACTIVE:
            h["status"] = "released"
    target["status"] = "confirmed"
    return target


def match_hold(holds: list[dict], thread_id: str, when: datetime) -> dict | None:
    for h in holds:
        if h.get("thread_id") == thread_id and h["status"] == "held":
            if abs((parse_dt(h["start"]) - when).total_seconds()) <= 30 * 60:
                return h
    return None
