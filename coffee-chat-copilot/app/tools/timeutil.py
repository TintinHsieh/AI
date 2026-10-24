from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def now() -> datetime:
    return datetime.now(TZ)


def parse_hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def at(d: date, hm: str | time) -> datetime:
    t = parse_hm(hm) if isinstance(hm, str) else hm
    return datetime.combine(d, t, tzinfo=TZ)


def parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def iso(dt: datetime) -> str:
    return dt.astimezone(TZ).isoformat(timespec="minutes")


def overlaps(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


def pretty(dt: datetime) -> str:
    return dt.strftime("%A, %B ") + str(dt.day) + ": " + clock(dt)


def clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def daterange(d0: date, d1: date):
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)
