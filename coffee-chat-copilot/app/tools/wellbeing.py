"""Wellbeing facts + rule-based nudges. The Coach agent only rephrases these."""
from datetime import timedelta

from . import dayplan
from .timeutil import DAY_NAMES, now, parse_dt

YALE_SUPPORT = "Yale Mental Health & Counseling: 203-432-0290 (24/7 for urgent support)"


def week_facts(profile: dict, holds: list[dict], threads: list[dict], checkins: list[dict]) -> dict:
    t = now()
    start = t.date()
    end = start + timedelta(days=6)
    days = {}
    for h in holds:
        if h["status"] != "confirmed":
            continue
        d = parse_dt(h["start"]).date()
        if start <= d <= end:
            days.setdefault(d, []).append(h)
    nyc_days = sorted({d for d, hs in days.items() if any(h["mode"] == "in_person" for h in hs)})
    late = []
    for d in nyc_days:
        p = dayplan.day_plan(profile, holds, d, include_held=False)
        if any("Late night" in f["text"] for f in p["flags"]):
            late.append(d)
    pending = [th for th in threads if th.get("status") == "reply_needed"]
    recent = sorted(checkins, key=lambda c: c["date"])[-3:]
    wb = profile.get("wellbeing", {})
    return {
        "today": t.date().isoformat(),
        "confirmed_chats_next_7_days": sum(len(v) for v in days.values()),
        "busiest_day": max(((DAY_NAMES[d.weekday()] + " " + d.isoformat(), len(v)) for d, v in days.items()), key=lambda x: x[1], default=None),
        "nyc_days": [d.isoformat() for d in nyc_days],
        "late_returns": [d.isoformat() for d in late],
        "pending_replies": len(pending),
        "max_chats_per_week": wb.get("max_chats_per_week", 6),
        "recent_checkins": recent,
        "favorite_treats": wb.get("favorite_treats", []),
        "friends": wb.get("friends", []),
        "sleep_goal_hours": wb.get("sleep_goal_hours", 7),
    }


def rule_nudges(f: dict) -> list[dict]:
    n = []
    treats = f["favorite_treats"] or ["something you love"]
    friends = f["friends"] or ["a friend"]
    if f["confirmed_chats_next_7_days"] >= f["max_chats_per_week"]:
        n.append({"kind": "pace", "text": f"You have {f['confirmed_chats_next_7_days']} chats this week, which is your limit. Don't offer new times until next week. Bankers will wait a few days."})
    for d in f["nyc_days"]:
        n.append({"kind": "treat", "text": f"NYC day on {d}. After your last chat, get {treats[0]} before the train. You earned it."})
    for d in f["late_returns"]:
        n.append({"kind": "rest", "text": f"You get back late on {d}. Skip the 9 AM grind the next day and sleep {f['sleep_goal_hours']} hours if you can."})
    if f["confirmed_chats_next_7_days"] >= 3:
        n.append({"kind": "friends", "text": f"Busy week. Text {friends[0]} and get a meal together that has nothing to do with banking."})
    rc = f["recent_checkins"]
    if rc:
        low = [c for c in rc if int(c.get("mood", 3)) <= 2]
        if len(low) >= 2:
            n.append({"kind": "support", "text": "Your last few check-ins were rough. Recruiting is a marathon, and talking to someone helps. " + YALE_SUPPORT})
        last = rc[-1]
        if not last.get("ate_well"):
            n.append({"kind": "food", "text": "You said you didn't eat well last time. Plan one real meal today. A dining hall dinner counts."})
        if float(last.get("slept_hours") or 8) < f["sleep_goal_hours"]:
            n.append({"kind": "rest", "text": f"You slept {last.get('slept_hours')}h. An early night tonight will make tomorrow's chats easier."})
        if not last.get("talked_to_friend"):
            n.append({"kind": "friends", "text": f"Call {friends[-1]} today, even for 10 minutes."})
    if f["pending_replies"]:
        n.append({"kind": "pace", "text": f"{f['pending_replies']} banker email(s) waiting. Clear them in one sitting, then close the inbox."})
    if not n:
        n.append({"kind": "food", "text": "Quiet week. Use it to rest, see friends, and eat well. Recruiting isn't only coffee chats."})
    return n[:6]
