"""Deterministic scheduling: classes, holds, trains, travel."""
from datetime import date, datetime, timedelta

from app import store
from app.tools import calendar as cal
from app.tools import nyc, trains
from app.tools.timeutil import TZ, at

NOW = datetime(2026, 10, 23, 20, 0, tzinfo=TZ)  # a Friday evening
MON, TUE, FRI = date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 30)


def profile():
    return store.load_profile()


def test_virtual_slot_blocked_by_class():
    p = profile()  # Core: Accounting Mon 08:30-09:50
    r = cal.check_slot(p, [], at(MON, "09:00"), "virtual", None, t_now=NOW)
    assert not r["ok"] and any("class" in x for x in r["reasons"])


def test_reasons_never_leak_class_names():
    p = profile()
    r = cal.check_slot(p, [], at(MON, "09:00"), "virtual", None, t_now=NOW)
    assert not any(c["name"] in " ".join(r["reasons"]) for c in p["classes"])


def test_in_person_needs_whole_trip_free():
    p = profile()  # Tue classes 10:10-11:30 and 14:40-16:00: a midday NYC chat can't fit
    r = cal.check_slot(p, [], at(TUE, "12:00"), "in_person", "Evercore", t_now=NOW)
    assert not r["ok"] and any("NYC trip overlaps" in x for x in r["reasons"])


def test_in_person_friday_has_real_trains():
    p = profile()
    r = cal.check_slot(p, [], at(FRI, "11:00"), "in_person", "Goldman Sachs", t_now=NOW)
    assert r["ok"], r["reasons"]
    plan = r["plan"]
    leg = nyc.travel(nyc.GCT, "Goldman Sachs")
    # arrives at GCT early enough to travel + arrive 15 min early
    assert plan["out_train"]["arrive"] + timedelta(minutes=leg["minutes"] + p["arrive_early_min"]) <= at(FRI, "11:00")
    assert plan["return_train"]["depart"] >= at(FRI, "12:30")
    assert plan["out_train"] in trains.trains_on(FRI, "to_nyc")


def test_holds_prevent_double_booking():
    p = profile()
    th = {"id": "th_a", "banker_name": "A", "bank": "Evercore"}
    holds = []
    slot = {"start": at(FRI, "13:00").isoformat(), "end": at(FRI, "14:30").isoformat(), "mode": "virtual"}
    cal.place_holds(holds, th, [slot], p)
    r = cal.check_slot(p, holds, at(FRI, "13:30"), "virtual", None, thread_id="th_b", t_now=NOW)
    assert not r["ok"] and any("hold" in x for x in r["reasons"])
    # the same banker's own hold does not block itself
    assert cal.check_slot(p, holds, at(FRI, "13:00"), "virtual", None, thread_id="th_a", t_now=NOW)["ok"]


def test_confirm_releases_sibling_holds():
    p = profile()
    th = {"id": "th_a", "banker_name": "A", "bank": "Evercore"}
    holds = []
    slots = [{"start": at(d, "16:00").isoformat(), "end": at(d, "17:30").isoformat(), "mode": "virtual"} for d in (MON, TUE, FRI)]
    new = cal.place_holds(holds, th, slots, p)
    cal.confirm_hold(holds, new[1]["id"])
    assert [h["status"] for h in holds] == ["released", "confirmed", "released"]


def test_two_banks_same_day_need_travel_time():
    p = profile()
    chats = [{"start": at(FRI, "10:00"), "end": at(FRI, "11:30"), "bank": "Goldman Sachs"},
             {"start": at(FRI, "11:40"), "end": at(FRI, "13:10"), "bank": "Evercore"}]
    assert "error" in cal.plan_trip(p, FRI, chats)  # 10 min is not enough to get downtown -> midtown
    chats[1]["start"], chats[1]["end"] = at(FRI, "12:30"), at(FRI, "14:00")
    assert "error" not in cal.plan_trip(p, FRI, chats)


def test_wellbeing_day_limit():
    p = profile()
    p["wellbeing"]["max_chats_per_day"] = 1
    holds = []
    cal.place_holds(holds, {"id": "th_a"}, [{"start": at(FRI, "09:00").isoformat(), "end": at(FRI, "10:30").isoformat(), "mode": "virtual"}], p)
    r = cal.check_slot(p, holds, at(FRI, "15:00"), "virtual", None, thread_id="th_b", t_now=NOW)
    assert any("wellbeing" in x for x in r["reasons"])


def test_find_open_slots_respects_banker_window():
    p = profile()
    res = cal.find_open_slots(p, [], MON, FRI, "virtual", weekdays=["Tue", "Thu"], earliest="12:00", latest="17:30", t_now=NOW)
    assert res
    for s in res:
        dt = datetime.fromisoformat(s["start"])
        assert dt.strftime("%a") in ("Tue", "Thu") and dt.hour >= 12
        assert cal.check_slot(p, [], dt, "virtual", None, t_now=NOW)["ok"]


def test_bank_alias_resolution():
    assert nyc.resolve_bank("GS")[0] == "Goldman Sachs"
    assert nyc.resolve_bank("Moelis & Co.")[0] == "Moelis & Company"
    assert nyc.resolve_bank("Totally Unknown LLC") is None
