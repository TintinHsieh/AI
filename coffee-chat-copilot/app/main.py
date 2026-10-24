"""FastAPI server for Coffee Chat Copilot. Run: python run.py"""
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, store
from .agents import Copilot
from .llm import BudgetExceeded, tokens_today
from .tools import calendar as cal
from .tools import dayplan, nyc
from .tools.timeutil import DAY_NAMES, at, clock, iso, now, parse_dt

app = FastAPI(title="Coffee Chat Copilot")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
copilot = Copilot()


@app.exception_handler(BudgetExceeded)
def _budget(_, exc: BudgetExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    s = copilot.llm.s
    return {"provider": s.provider, "model": s.model, "demo_mode": s.provider == "mock",
            "tokens_today": tokens_today(), "daily_token_budget": s.daily_token_budget,
            "run_token_budget": s.run_token_budget, "max_llm_calls_per_run": s.max_llm_calls_per_run,
            "now": iso(now())}


# ------------------------------------------------------------ settings
@app.get("/api/profile")
def get_profile():
    return store.load_profile()


@app.put("/api/profile")
def put_profile(p: dict):
    for k in ("name", "school", "classes", "chat_block_min"):
        if k not in p:
            raise HTTPException(400, f"missing {k}")
    store.save_profile(p)
    return p


class TemplateIn(BaseModel):
    key: str
    text: str


@app.get("/api/templates")
def get_templates():
    return store.load_templates()


@app.put("/api/templates")
def put_template(t: TemplateIn):
    try:
        store.save_template(t.key, t.text)
    except KeyError:
        raise HTTPException(400, "unknown template")
    return {"ok": True}


# ------------------------------------------------------------ inbox / threads
class EmailIn(BaseModel):
    email: str
    received_at: str | None = None
    thread_id: str | None = None


@app.post("/api/inbox")
def inbox(e: EmailIn):
    if not e.email.strip():
        raise HTTPException(400, "paste the banker's email first")
    return copilot.process_email(e.email, e.received_at, e.thread_id)


class OutreachIn(BaseModel):
    banker_name: str
    bank: str | None = None
    event: str | None = None
    referrer: str | None = None
    mode: str = "either"
    banker_email: str | None = None


@app.post("/api/outreach")
def outreach(o: OutreachIn):
    if not o.banker_name.strip():
        raise HTTPException(400, "banker name is required")
    return copilot.compose_outreach(o.banker_name.strip(), o.bank, o.event, o.referrer, o.mode, o.banker_email)


class EventThanksIn(BaseModel):
    banker_name: str
    bank: str | None = None
    event: str
    notes: str
    when: str = "yesterday"


@app.post("/api/event_thank_you")
def event_thanks(e: EventThanksIn):
    return copilot.event_thank_you(e.banker_name.strip(), e.bank, e.event, e.notes, e.when)


@app.get("/api/threads")
def threads():
    ths = store.load("threads.json", [])
    t = now()
    for th in ths:
        due = th.get("follow_up_due")
        th["follow_up_ready"] = bool(due and th.get("status") == "awaiting_banker" and parse_dt(due) <= t)
    return ths


def _get_thread(ths, tid):
    th = next((t for t in ths if t["id"] == tid), None)
    if not th:
        raise HTTPException(404, "thread not found")
    return th


@app.post("/api/threads/{tid}/steps/{sid}/sent")
def mark_sent(tid: str, sid: str):
    profile = store.load_profile()
    holds, ths = copilot.state()
    th = _get_thread(ths, tid)
    st = next((s for s in th["steps"] if s["id"] == sid), None)
    if not st:
        raise HTTPException(404, "step not found")
    st["sent_at"] = iso(now())
    if st.get("received_at"):
        st["reply_minutes"] = round((now() - parse_dt(st["received_at"])).total_seconds() / 60, 1)
    key = st.get("template_key", "")
    if key in ("outreach_intro", "outreach_no_intro", "follow_up_no_response", "availability_reply", "time_conflict"):
        th["status"] = "awaiting_banker"
        th["follow_up_due"] = iso(now() + timedelta(days=profile.get("follow_up_after_days", 3)))
    elif key in ("invite_virtual", "invite_in_person"):
        th["status"] = "scheduled"
        if st.get("matched_hold"):
            h = cal.confirm_hold(holds, st["matched_hold"])
            if h and st.get("confirmed_option", {}).get("mode") == "in_person":
                h["mode"] = "in_person"
        elif st.get("confirmed_option"):
            o = st["confirmed_option"]
            new = cal.place_holds(holds, th, [o], profile)
            new[0]["status"] = "confirmed"
    elif key == "thank_you_for_intro":
        th["status"] = "done"
    copilot.save(holds, ths)
    return th


@app.delete("/api/threads/{tid}")
def delete_thread(tid: str):
    holds, ths = copilot.state()
    for h in holds:
        if h.get("thread_id") == tid and h["status"] == "held":
            h["status"] = "released"
    copilot.save(holds, [t for t in ths if t["id"] != tid])
    return {"ok": True}


@app.post("/api/threads/{tid}/follow_up")
def follow_up(tid: str):
    try:
        return copilot.follow_up(tid)
    except KeyError:
        raise HTTPException(404, "thread not found")


class LateIn(BaseModel):
    location: str


@app.post("/api/threads/{tid}/late")
def late(tid: str, l: LateIn):
    try:
        return copilot.running_late(tid, l.location)
    except KeyError:
        raise HTTPException(404, "thread not found")


class NotesIn(BaseModel):
    notes: str
    when: str = "yesterday"


@app.post("/api/threads/{tid}/thank_you")
def thank_you(tid: str, n: NotesIn):
    try:
        return copilot.thank_you(tid, n.notes, n.when)
    except KeyError:
        raise HTTPException(404, "thread not found")


# ------------------------------------------------------------ holds + calendar
@app.get("/api/holds")
def holds():
    hs, _ = copilot.state()
    return [h for h in hs if h["status"] in ("held", "confirmed")]


@app.post("/api/holds/{hid}/confirm")
def confirm(hid: str):
    hs, ths = copilot.state()
    h = cal.confirm_hold(hs, hid)
    if not h:
        raise HTTPException(404, "hold not found")
    for t in ths:
        if t["id"] == h["thread_id"]:
            t["status"] = "confirmed"
            t["confirmed_hold"] = hid
    copilot.save(hs, ths)
    return h


@app.post("/api/holds/{hid}/release")
def release(hid: str):
    hs, ths = copilot.state()
    for h in hs:
        if h["id"] == hid:
            h["status"] = "released"
    copilot.save(hs, ths)
    return {"ok": True}


class ManualChat(BaseModel):
    banker: str
    bank: str | None = None
    mode: str = "virtual"
    start: str


@app.post("/api/holds/manual")
def manual(c: ManualChat):
    """Add an already-confirmed chat by hand (e.g., arranged by phone)."""
    profile = store.load_profile()
    hs, ths = copilot.state()
    st = parse_dt(c.start)
    chk = cal.check_slot(profile, hs, st, "in_person" if c.mode == "in_person" else "virtual", c.bank)
    th = copilot._new_thread(banker_name=c.banker, banker_first_name=c.banker.split()[0], bank=(nyc.resolve_bank(c.bank) or (c.bank,))[0],
                             mode=c.mode, status="scheduled")
    new = cal.place_holds(hs, th, [{"start": iso(st), "end": iso(chk["end"]), "mode": c.mode, "bank": th["bank"]}], profile)
    new[0]["status"] = "confirmed"
    ths.insert(0, th)
    copilot.save(hs, ths)
    return {"hold": new[0], "warnings": chk["reasons"]}


@app.get("/api/calendar")
def calendar(start: str | None = None, days: int = 7):
    profile = store.load_profile()
    hs, _ = copilot.state()
    d0 = date.fromisoformat(start) if start else now().date()
    out = []
    for i in range(min(days, 21)):
        d = d0 + timedelta(days=i)
        for b in cal.fixed_busy(profile, d):
            out.append({"kind": b["kind"], "title": b["label"], "start": iso(b["start"]), "end": iso(b["end"])})
        p = dayplan.day_plan(profile, hs, d, include_held=False)
        if p["trip"]:
            steps = p["steps"]
            out.append({"kind": "travel", "title": "NYC trip (train + travel)", "start": iso(at(d, _hm(steps[0]["time"]))),
                        "end": iso(at(d, _hm(steps[-1]["time"])) if _hm(steps[-1]["time"]) > _hm(steps[0]["time"]) else at(d, "23:59"))})
    for h in hs:
        if h["status"] in ("held", "confirmed") and d0 <= parse_dt(h["start"]).date() < d0 + timedelta(days=days):
            out.append({"kind": h["status"], "title": h.get("label"), "start": h["start"], "end": h["end"], "id": h["id"],
                        "mode": h["mode"], "bank": h.get("bank"), "thread_id": h["thread_id"]})
    return {"start": d0.isoformat(), "days": days, "events": out}


def _hm(s: str) -> str:
    from datetime import datetime
    return datetime.strptime(s, "%I:%M %p").strftime("%H:%M")


@app.get("/api/slots")
def slots(mode: str = "virtual", bank: str | None = None, start: str | None = None, end: str | None = None):
    profile = store.load_profile()
    hs, _ = copilot.state()
    s = date.fromisoformat(start) if start else now().date() + timedelta(days=1)
    e = date.fromisoformat(end) if end else s + timedelta(days=9)
    return cal.find_open_slots(profile, hs, s, e, mode, bank, limit=12)


@app.get("/api/dayplan")
def get_dayplan(day: str, include_held: bool = True):
    profile = store.load_profile()
    hs, _ = copilot.state()
    return dayplan.day_plan(profile, hs, date.fromisoformat(day), include_held)


@app.get("/api/nyc_days")
def nyc_days():
    profile = store.load_profile()
    hs, _ = copilot.state()
    ds = dayplan.upcoming_nyc_days(profile, hs)
    return {"days": ds, "best": dayplan.best_nyc_day(hs, ds)}


@app.get("/api/banks")
def banks():
    return [{"name": k, "address": v["address"]} for k, v in nyc.offices().items() if k != nyc.GCT]


@app.get("/api/ics/{hid}")
def ics(hid: str):
    hs, _ = copilot.state()
    h = next((x for x in hs if x["id"] == hid), None)
    if not h:
        raise HTTPException(404, "hold not found")
    fmt = lambda s: parse_dt(s).astimezone(__import__("zoneinfo").ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    loc = nyc.office_address(h.get("bank")) if h["mode"] == "in_person" else "Video/phone call"
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Coffee Chat Copilot//EN", "BEGIN:VEVENT",
        f"UID:{hid}@coffeechatcopilot", f"DTSTAMP:{fmt(iso(now()))}", f"DTSTART:{fmt(h['start'])}", f"DTEND:{fmt(h['end'])}",
        f"SUMMARY:{h.get('label', 'Coffee chat')}{' (HOLD)' if h['status'] == 'held' else ''}", f"LOCATION:{loc}",
        "END:VEVENT", "END:VCALENDAR", ""])
    return Response(body, media_type="text/calendar", headers={"Content-Disposition": f'attachment; filename="{hid}.ics"'})


# ------------------------------------------------------------ usage / tokenomics
@app.get("/api/usage")
def usage():
    recs = store.read_jsonl("usage.jsonl")
    s = copilot.llm.s
    runs = {}
    for r in recs:
        if r.get("provider") == "mock" and s.provider != "mock":
            continue
        runs.setdefault(r["run"], []).append(r)
    keys = ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "cost_usd")
    by_agent = {}
    for r in recs:
        a = by_agent.setdefault(r["agent"], {k: 0 for k in keys} | {"calls": 0})
        for k in keys:
            a[k] += r.get(k, 0)
        a["calls"] += 1
    threads = store.load("threads.json", [])
    steps = [st for t in threads for st in t.get("steps", []) if st.get("usage", {}).get("llm_calls")]
    if s.provider != "mock":
        steps = [st for st in steps if all(c.get("provider") != "mock" for c in st["usage"].get("by_agent", []))]
    inbox_runs = [st["usage"] for st in steps if st["kind"] == "inbound"]
    avg = lambda k: (sum(u[k] for u in inbox_runs) / len(inbox_runs)) if inbox_runs else 0
    per_run = {k: round(avg(k), 1) for k in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "llm_calls", "seconds")}
    per_run["cost_usd"] = round(avg("cost_usd"), 6)
    kind_cost = {}
    for st in steps:
        kind_cost.setdefault(st["kind"], []).append(st["usage"]["cost_usd"])
    mean = lambda k, default: (sum(kind_cost[k]) / len(kind_cost[k])) if kind_cost.get(k) else default
    coach = by_agent.get("coach", {})
    coach_cost = (coach.get("cost_usd", 0) / coach["calls"]) if coach.get("calls") else per_run["cost_usd"] * 0.15
    # a recruiting month per user: 20 outreach emails, 6 follow-ups, 25 banker replies, 10 thank-yous, 10 coach refreshes
    monthly = (20 * mean("outreach", per_run["cost_usd"]) + 6 * mean("follow_up", per_run["cost_usd"]) + 25 * per_run["cost_usd"]
               + 10 * mean("thank_you", per_run["cost_usd"] * 0.4) + 10 * coach_cost)
    return {"provider": s.provider, "model": s.model, "records": recs[-200:], "by_agent": by_agent,
            "inbox_runs": len(inbox_runs), "avg_inbox_run": per_run,
            "monthly_per_user_usd": round(monthly, 4),
            "scale": {"100_users": round(monthly * 100, 2), "10000_users": round(monthly * 10000, 2)},
            "assumptions": "per user per month: 20 outreach, 6 follow-ups, 25 banker replies, 10 thank-yous, 10 coach refreshes",
            "avg_cost_by_kind": {k: round(sum(v) / len(v), 6) for k, v in kind_cost.items()},
            "totals": {k: round(sum(r.get(k, 0) for r in recs), 6) for k in keys}}


# ------------------------------------------------------------ wellbeing
class CoachIn(BaseModel):
    use_llm: bool = True


@app.post("/api/coach")
def coach(c: CoachIn):
    return copilot.coach(c.use_llm)


class CheckIn(BaseModel):
    mood: int
    slept_hours: float
    ate_well: bool
    talked_to_friend: bool
    note: str | None = ""


@app.get("/api/checkins")
def get_checkins():
    return store.load("checkins.json", [])


@app.post("/api/checkins")
def add_checkin(c: CheckIn):
    items = [x for x in store.load("checkins.json", []) if x["date"] != now().date().isoformat()]
    items.append({"date": now().date().isoformat(), **c.model_dump()})
    store.save("checkins.json", items)
    return items


# ------------------------------------------------------------ demo helpers
@app.get("/api/samples")
def samples():
    out = []
    for p in sorted((config.DATA_DIR / "sample_emails").glob("*.txt")):
        out.append({"name": p.stem.replace("_", " ")[3:].title(), "text": p.read_text(encoding="utf-8")})
    return out


@app.post("/api/reset")
def reset():
    for name in ("holds.json", "threads.json", "checkins.json"):
        store.save(name, [])
    return {"ok": True}
