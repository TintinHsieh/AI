"""The four agents and the pipelines that connect them.

Banker email in:
  [Guard: rate limit, size cap, injection scan]                       (Python)
  -> Intake agent      (LLM, structured JSON)
  -> route by request type:
       asks for times / reschedule -> Scheduler agent (LLM + read-only tools) -> Validator (Python)
                                      -> Responder (availability_reply template)
       picks a time                -> Validator: is it one of our holds / free?
                                      -> Responder (invite_virtual / invite_in_person) or time_conflict + new options
       introduces another banker   -> Responder (thank_you_for_intro) + suggested outreach to the new banker
  -> Draft checker (Python) -> one retry -> deterministic template fallback
  -> holds placed (Python)

Student-initiated: outreach (intro / no intro), follow-up after no response, running-late note,
thank-you after a chat or an event. Wellbeing Coach agent runs on demand.
"""
import json
import re
from datetime import date, timedelta

from . import prompts, safety, store
from .llm import LLM, BudgetExceeded, Run, output_text, parse_json
from .tools import calendar as cal
from .tools import nyc, trains, wellbeing
from .tools.timeutil import DAY_NAMES, clock, iso, now, parse_dt

MODE_LABEL = {"in_person": "in-person", "virtual": "virtual", "phone": "phone", "either": "in-person or virtual"}


# ------------------------------------------------------------------ formatting
def md(dt) -> str:
    return f"{dt.month}/{dt.day}"


def option_line(slot: dict) -> str:
    """Club format: '- Tuesday, 9/8: 3:00 PM – 4:30 PM ET (in-person or virtual)'"""
    s, e = parse_dt(slot["start"]), parse_dt(slot["end"])
    label = MODE_LABEL.get(slot.get("offer_mode") or slot.get("mode"), "virtual")
    return f"- {s.strftime('%A')}, {md(s)}: {clock(s)} – {clock(e)} ET ({label})"


def confirmed_line(slot: dict) -> str:
    s = parse_dt(slot["start"])
    return f"{s.strftime('%A')}, {md(s)} at {clock(s)} ET"


def signature(profile: dict) -> str:
    contact = " | ".join(x for x in [profile.get("phone"), profile.get("email")] if x)
    lines = [profile.get("sign_off", "Best,"), "", profile["name"], profile.get("title_line") or profile.get("school", "")]
    if contact:
        lines.append(contact)
    return "\n".join(lines)


def split_template(text: str) -> tuple[str | None, str]:
    subject, body = None, []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if subject is None and not body and line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            continue
        body.append(line)
    return subject, "\n".join(body).strip()


def render(template: str, values: dict) -> dict:
    subject, body = split_template(template)
    fill = lambda t: re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1)) or m.group(0)), t)
    body = fill(body)
    body = re.sub(r"\{(\w+)\}", "", body)  # drop any placeholder we had no value for
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return {"subject": fill(subject) if subject else "Re: Coffee Chat", "body": body}


def first_name(name: str | None) -> str | None:
    return name.split()[0] if name else None


def fallback_specifics(notes: str) -> str:
    bits = [b.strip(" .-") for b in re.split(r"[\n;]|\. ", notes or "") if b.strip(" .-")]
    if not bits:
        return "I especially enjoyed hearing about your experience."
    out = f"I especially enjoyed hearing about {bits[0][0].lower() + bits[0][1:]}."
    if len(bits) > 1:
        b = bits[1][0].lower() + bits[1][1:]
        out += f" I also appreciated your {b}." if b.startswith("advice") else f" I also appreciated your point about {b}."
    return out


def fallback_intake(email: str, today: date) -> dict:
    """Regex extraction used in demo mode and when the model output can't be parsed."""
    low = email.lower()
    bank = None
    for canon, info in nyc.offices().items():
        if canon == nyc.GCT:
            continue
        for n in [canon] + [a for a in info.get("aliases", []) if len(a) > 3]:
            if re.search(r"\b" + re.escape(n.lower()) + r"\b", low):
                bank = canon
                break
        if bank:
            break
    name = None
    m = re.search(r"(?:best|regards|thanks|cheers|sincerely|best regards|all the best)[,!.]?\s*\n+\s*([A-Z][a-z]+(?: [A-Z][a-zA-Z'\-]+)+)", email, flags=re.I)
    if m:
        name = m.group(1).strip()
    mode = "in_person" if re.search(r"in[- ]person|our office|stop by|come by|grab (a )?coffee|in the city|at the office|swing by", low) else \
        ("phone" if re.search(r"\bphone\b|\bcall you\b|give you a call", low) else ("virtual" if re.search(r"zoom|teams|video|virtual", low) else "unknown"))
    intro = re.search(r"(?:introduc\w+|connect\w*) (?:you )?(?:to|with) ([A-Z][a-z]+(?: [A-Z][a-zA-Z'\-]+)+)", email)
    if intro:
        rtype = "introduction"
    elif re.search(r"works (great|for me|well)|let'?s do|see you (on|then)|i'?ll take|confirm(ed)?\b", low):
        rtype = "time_confirmation"
    elif re.search(r"reschedul|move our|push our|something came up", low):
        rtype = "reschedule"
    elif re.search(r"great (chatting|speaking|meeting)|pleasure (chatting|speaking)", low):
        rtype = "thank_you_reply"
    else:
        rtype = "new_outreach"
    avail = []
    for i, day in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday"]):
        if day in low:
            d = today + timedelta(days=(i - today.weekday()) % 7 or 7)
            avail.append({"date": d.isoformat(), "weekday": DAY_NAMES[i], "earliest": None, "latest": None, "note": day})
    m_before = re.search(r"before (1[0-2]|[1-9])(?::([0-5]\d))?\s*([ap])?", low)
    window = None
    if "morning" in low or m_before:
        latest = "12:00"
        if m_before:
            h = int(m_before.group(1)) % 12 + (12 if m_before.group(3) == "p" else 0)
            latest = f"{h:02d}:{m_before.group(2) or '00'}"
        window = {"earliest": None, "latest": latest, "note": "morning"}
    elif "afternoon" in low:
        window = {"earliest": "12:00", "latest": "17:30", "note": "afternoon"}
    if window:
        if avail:
            for a in avail:
                a.update({k: v for k, v in window.items() if k != "note"})
        else:
            avail.append({"date": None, "weekday": None, **window})
    confirmed = None
    tm = re.search(r"\b(1[0-2]|[1-9])(?::([0-5]\d))?\s*([ap])\.?m", low)
    dm = re.search(r"\b(1[0-2]|[1-9])/([12]\d|3[01]|[1-9])\b", email)
    if rtype in ("time_confirmation", "reschedule") and tm and (avail or dm):
        try:
            if dm:
                d = date(today.year, int(dm.group(1)), int(dm.group(2)))
                if d < today - timedelta(days=60):
                    d = date(today.year + 1, d.month, d.day)
            else:
                d = date.fromisoformat(avail[0]["date"])
            h = int(tm.group(1)) % 12 + (12 if tm.group(3) == "p" else 0)
            confirmed = iso(parse_dt(d.isoformat() + "T00:00").replace(hour=h, minute=int(tm.group(2) or 0)))
        except (ValueError, TypeError):  # e.g. "11/31": impossible date, treat as no confirmed time
            confirmed = None
    return {
        "banker_name": name, "banker_first_name": first_name(name), "banker_title": None, "bank": bank,
        "banker_email": (re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", email) or [None])[0], "request_type": rtype, "mode": mode,
        "banker_availability": avail, "confirmed_time": confirmed,
        "date_window": {"start": (today + timedelta(days=1)).isoformat(), "end": (today + timedelta(days=10)).isoformat()},
        "location_note": None, "introduced_name": intro.group(1) if intro else None, "introduced_email": None,
        "suspicious": False, "suspicious_reason": None,
        "summary": f"{name or 'A banker'}{' from ' + bank if bank else ''}: {rtype.replace('_', ' ')}.",
    }


def ctx_msg(obj: dict) -> dict:
    return {"role": "user", "content": "CONTEXT_JSON:\n" + json.dumps(obj, default=str)}


# ------------------------------------------------------------------ copilot
class Copilot:
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or LLM()
        self.limiter = safety.RateLimiter(self.llm.s.max_runs_per_minute)
        self._availability = []

    # ---------- state
    def state(self):
        return cal.refresh_holds(store.load("holds.json", [])), store.load("threads.json", [])

    def save(self, holds, threads):
        store.save("holds.json", holds)
        store.save("threads.json", threads)

    def _allow(self):
        if not self.limiter.allow():
            raise BudgetExceeded("rate limit: too many runs in the last minute, wait a moment")

    @staticmethod
    def _new_thread(**kw) -> dict:
        t = iso(now())
        th = {"id": store.new_id("th"), "created_at": t, "updated_at": t, "status": "new", "steps": [],
              "banker_name": None, "banker_first_name": None, "bank": None, "mode": "virtual"}
        th.update(kw)
        return th

    @staticmethod
    def _find_thread(threads, thread_id=None, banker_name=None):
        if thread_id:
            return next((t for t in threads if t["id"] == thread_id), None)
        if banker_name:
            return next((t for t in threads if (t.get("banker_name") or "").lower() == banker_name.lower()), None)
        return None

    # ================================================================ banker email in
    def process_email(self, email: str, received_at: str | None = None, thread_id: str | None = None) -> dict:
        self._allow()
        profile = store.load_profile()
        run, trace, t = Run("inbox"), [], now()
        received = parse_dt(received_at) if received_at else t
        if len(email) > self.llm.s.max_email_chars:
            email = email[: self.llm.s.max_email_chars]
            trace.append({"agent": "Guard", "step": "truncated", "detail": f"email cut to {self.llm.s.max_email_chars} chars"})
        scan = safety.scan(email)
        trace.append({"agent": "Guard", "step": "injection scan", "detail": f"risk={scan['risk']}", "data": scan["hits"]})
        holds, threads = self.state()
        step = {"id": store.new_id("st"), "kind": "inbound", "ts": iso(t), "received_at": iso(received),
                "deadline": iso(received + timedelta(minutes=profile.get("reply_sla_min", 15))),
                "email": email, "trace": trace, "safety": {"scan": scan}}
        thread = None
        try:
            ex = self.intake(run, email, t.date(), trace)
            if scan["risk"] == "high":
                ex["suspicious"] = True
                ex["suspicious_reason"] = ex.get("suspicious_reason") or "; ".join(h["label"] for h in scan["hits"])
            step["extracted"] = ex
            thread = self._find_thread(threads, thread_id, ex.get("banker_name"))
            if thread is None:
                thread = self._new_thread()
                threads.insert(0, thread)
            resolved = nyc.resolve_bank(ex.get("bank") or thread.get("bank"))
            thread.update({k: v for k, v in {
                "banker_name": ex.get("banker_name") or thread.get("banker_name"),
                "banker_first_name": ex.get("banker_first_name") or first_name(ex.get("banker_name")) or thread.get("banker_first_name"),
                "bank": resolved[0] if resolved else (ex.get("bank") or thread.get("bank")),
                "banker_email": ex.get("banker_email") or thread.get("banker_email"),
            }.items() if v})
            if ex.get("mode") in ("in_person", "virtual", "phone"):
                thread["mode"] = ex["mode"]
            if ex.get("suspicious"):
                thread["suspicious"] = True
            self._route(run, profile, ex, step, thread, holds, threads, trace)
        except Exception as e:  # budget stop, or anything unexpected: never crash, tell the user
            msg = str(e) if isinstance(e, BudgetExceeded) else f"unexpected error ({type(e).__name__}); please reply by hand this time"
            trace.append({"agent": "Guard", "step": "stopped", "detail": msg})
            step["error"] = msg
            if thread is None:
                thread = self._new_thread(banker_name="(stopped)")
                threads.insert(0, thread)
        step["usage"] = run.summary()
        step["draft_ready_seconds"] = step["usage"]["seconds"]
        thread["steps"].append(step)
        thread["updated_at"] = iso(now())
        threads.remove(thread)
        threads.insert(0, thread)
        self.save(holds, threads)
        return thread

    def _route(self, run, profile, ex, step, thread, holds, threads, trace):
        rtype = ex.get("request_type") or "new_outreach"
        mode = thread.get("mode") if thread.get("mode") in ("in_person", "virtual", "phone") else "virtual"
        sched_mode = "in_person" if mode == "in_person" else "virtual"
        base = self._values(profile, thread)

        if rtype == "thank_you_reply":
            trace.append({"agent": "Orchestrator", "step": "no reply needed", "detail": "banker replied to a thank-you; nothing to schedule"})
            step["draft"] = None
            thread["status"] = "done"
            return

        if rtype == "introduction":
            new = ex.get("introduced_name") or "them"
            step["template_key"] = "thank_you_for_intro"
            self.respond(run, profile, "thank_you_for_intro", {**base, "new_banker": new}, [], None, trace, step, own_bank=thread.get("bank"))
            step["suggested_outreach"] = {"banker_name": ex.get("introduced_name"), "banker_email": ex.get("introduced_email"),
                                          "bank": thread.get("bank"), "referrer": thread.get("banker_name")}
            trace.append({"agent": "Orchestrator", "step": "next step", "detail": f"suggest an outreach email to {new} (referred by {thread.get('banker_name')})"})
            thread["status"] = "reply_needed"
            return

        when = None
        if rtype == "time_confirmation" and ex.get("confirmed_time"):
            try:
                when = parse_dt(ex["confirmed_time"])
            except (ValueError, TypeError):
                trace.append({"agent": "Validator", "step": "bad time", "detail": f"could not read {ex['confirmed_time']!r}; offering times instead"})
                rtype = "new_outreach"
        if when is not None:
            ok, why = safety.time_grounded(step.get("email", ""), when, now().date())
            if not ok:  # never confirm a time the banker didn't actually write
                trace.append({"agent": "Validator", "step": "pick not confirmed", "detail": f"AI read the pick as {when.isoformat()} but {why}; offering validated times instead"})
                step["ungrounded_pick"] = {"ai_read": iso(when), "reason": why}
                when, rtype = None, "new_outreach"
        if when is not None:
            hold = cal.match_hold(holds, thread["id"], when) or next(
                (h for h in holds if h["status"] == "held" and abs((parse_dt(h["start"]) - when).total_seconds()) <= 1800), None)
            if hold and ex.get("mode") not in ("in_person", "virtual", "phone"):
                mode = "in_person" if hold["mode"] == "in_person" else "virtual"
                sched_mode = mode
            chk = cal.check_slot(profile, holds, when, sched_mode, thread.get("bank"), thread["id"])
            pub = cal.slot_public(chk)
            pub["mode"] = mode
            trace.append({"agent": "Validator", "step": "banker's pick",
                          "detail": f"matches your hold {hold['id']}" if hold else ("time is free" if chk["ok"] else "conflict: " + "; ".join(chk["reasons"])),
                          "data": pub})
            if hold or chk["ok"]:
                step["confirmed_option"] = pub
                step["matched_hold"] = hold["id"] if hold else None
                key = "invite_in_person" if mode == "in_person" else "invite_virtual"
                step["template_key"] = key
                vals = {**base, "confirmed_time": confirmed_line(pub), "meeting_details": profile.get("zoom_details", "")}
                self.respond(run, profile, key, vals, [], pub, trace, step, own_bank=thread.get("bank"))
                thread["status"] = "reply_needed"
                return
            trace.append({"agent": "Orchestrator", "step": "conflict", "detail": "banker's time doesn't work; offering alternatives instead of confirming"})
            rtype = "time_conflict"

        options = self.schedule(run, profile, ex, sched_mode, thread.get("bank"), thread["id"], holds, trace)
        for o in options:
            o["mode"] = sched_mode
            o["bank"] = thread.get("bank")
        step["options"] = options
        key = "time_conflict" if rtype == "time_conflict" else "availability_reply"
        step["template_key"] = key
        vals = {**base, "options": "\n".join(option_line(o) for o in options)}
        self.respond(run, profile, key, vals, options, None, trace, step, own_bank=thread.get("bank"))
        new = cal.place_holds(holds, thread, options, profile)
        trace.append({"agent": "Orchestrator", "step": "holds placed",
                      "detail": f"{len(new)} tentative holds (expire in {profile.get('hold_expiry_hours', 48)}h) so no other banker gets these times"})
        thread["status"] = "reply_needed"

    @staticmethod
    def _values(profile, thread) -> dict:
        return {"banker_first_name": thread.get("banker_first_name") or first_name(thread.get("banker_name")) or "there",
                "banker_name": thread.get("banker_name") or "", "bank": thread.get("bank") or "",
                "event": thread.get("event") or "", "referrer": thread.get("referrer") or "",
                "my_name": profile["name"], "signature": signature(profile)}

    # ================================================================ student-initiated
    def compose_outreach(self, banker_name: str, bank: str | None, event: str | None, referrer: str | None,
                         mode: str = "either", banker_email: str | None = None) -> dict:
        self._allow()
        profile = store.load_profile()
        holds, threads = self.state()
        run, trace = Run("outreach"), []
        resolved = nyc.resolve_bank(bank)
        thread = self._find_thread(threads, None, banker_name) or self._new_thread()
        if thread not in threads:
            threads.insert(0, thread)
        thread.update({"banker_name": banker_name, "banker_first_name": first_name(banker_name),
                       "bank": resolved[0] if resolved else bank, "event": event or (f"{bank} Corporate Presentation" if bank else "corporate presentation"),
                       "referrer": referrer or None, "mode": "in_person" if mode == "in_person" else "virtual",
                       "offer_mode": mode, "banker_email": banker_email})
        step = {"id": store.new_id("st"), "kind": "outreach", "ts": iso(now()), "trace": trace, "safety": {}}
        try:
            options = self._offer_options(run, profile, thread, holds, mode, trace, purpose="outreach")
            step["options"] = options
            key = "outreach_intro" if referrer else "outreach_no_intro"
            step["template_key"] = key
            vals = {**self._values(profile, thread), "options": "\n".join(option_line(o) for o in options)}
            self.respond(run, profile, key, vals, options, None, trace, step, own_bank=thread.get("bank"))
            cal.place_holds(holds, thread, options, profile)
            trace.append({"agent": "Orchestrator", "step": "holds placed", "detail": f"{len(options)} windows held until the banker replies"})
        except BudgetExceeded as e:
            step["error"] = str(e)
            trace.append({"agent": "Guard", "step": "budget stop", "detail": str(e)})
        step["usage"] = run.summary()
        thread["steps"].append(step)
        thread["status"] = "draft_outreach"
        thread["updated_at"] = iso(now())
        self.save(holds, threads)
        return thread

    def follow_up(self, thread_id: str) -> dict:
        self._allow()
        profile = store.load_profile()
        holds, threads = self.state()
        thread = self._find_thread(threads, thread_id)
        if not thread:
            raise KeyError(thread_id)
        run, trace = Run("follow_up"), []
        step = {"id": store.new_id("st"), "kind": "follow_up", "ts": iso(now()), "trace": trace, "safety": {}}
        try:
            options = self._offer_options(run, profile, thread, holds, thread.get("offer_mode", "either"), trace, purpose="follow_up")
            step["options"] = options
            step["template_key"] = "follow_up_no_response"
            vals = {**self._values(profile, thread), "options": "\n".join(option_line(o) for o in options)}
            self.respond(run, profile, "follow_up_no_response", vals, options, None, trace, step, own_bank=thread.get("bank"))
            cal.place_holds(holds, thread, options, profile)  # releases the stale holds first
        except BudgetExceeded as e:
            step["error"] = str(e)
        step["usage"] = run.summary()
        thread["steps"].append(step)
        thread["status"] = "draft_outreach"
        thread["updated_at"] = iso(now())
        self.save(holds, threads)
        return thread

    def _offer_options(self, run, profile, thread, holds, mode, trace, purpose):
        """Scheduler agent picks windows; for 'either', label each as in-person-capable or virtual-only."""
        sched_mode = "in_person" if mode == "in_person" else "virtual"
        today = now().date()
        ex = {"banker_availability": [], "request_type": purpose,
              "date_window": {"start": (today + timedelta(days=1)).isoformat(), "end": (today + timedelta(days=8)).isoformat()}}
        options = self.schedule(run, profile, ex, sched_mode, thread.get("bank"), thread["id"], holds, trace)
        for o in options:
            o["bank"] = thread.get("bank")
            o["mode"] = sched_mode
            if mode == "either":
                ip = cal.check_slot(profile, holds, parse_dt(o["start"]), "in_person", thread.get("bank"), thread["id"])
                o["offer_mode"] = "either" if ip["ok"] else "virtual"
        if mode == "either" and options and not any(o["offer_mode"] == "either" for o in options):
            # make sure at least one window also works in person (usually a class-free day)
            ws = date.fromisoformat(ex["date_window"]["start"])
            pool = cal.find_open_slots(profile, holds, ws, ws + timedelta(days=13), "in_person", thread.get("bank"), thread["id"], limit=4)
            pick = next((p for p in pool if not any(p["start"][:10] == o["start"][:10] for o in options[:-1])), None)
            if pick:
                pick.update({"bank": thread.get("bank"), "mode": "virtual", "offer_mode": "either", "why": "works in person too"})
                options = sorted(options[:-1] + [pick], key=lambda o: o["start"])
                trace.append({"agent": "Validator", "step": "in-person option", "detail": f"swapped in {pick['label']} so one window works in NYC"})
        return options

    def running_late(self, thread_id: str, location: str) -> dict:
        """Deterministic, zero tokens: it has to go out in seconds while you're standing in a lobby."""
        profile = store.load_profile()
        holds, threads = self.state()
        thread = self._find_thread(threads, thread_id)
        if not thread:
            raise KeyError(thread_id)
        tpl = store.load_templates()["running_late"]
        draft = render(tpl, {**self._values(profile, thread), "location": location.strip()[:120] or "lobby"})
        step = {"id": store.new_id("st"), "kind": "running_late", "ts": iso(now()), "template_key": "running_late",
                "draft": draft, "draft_source": "template (no AI)", "trace": [], "usage": Run("late").summary()}
        thread["steps"].append(step)
        self.save(holds, threads)
        return thread

    def thank_you(self, thread_id: str, notes: str, when: str = "yesterday") -> dict:
        self._allow()
        profile = store.load_profile()
        holds, threads = self.state()
        thread = self._find_thread(threads, thread_id)
        if not thread:
            raise KeyError(thread_id)
        return self._thank(profile, holds, threads, thread, "thank_you_post_chat", notes, when)

    def event_thank_you(self, banker_name: str, bank: str | None, event: str, notes: str, when: str = "yesterday") -> dict:
        self._allow()
        profile = store.load_profile()
        holds, threads = self.state()
        resolved = nyc.resolve_bank(bank)
        thread = self._find_thread(threads, None, banker_name) or self._new_thread()
        if thread not in threads:
            threads.insert(0, thread)
        thread.update({"banker_name": banker_name, "banker_first_name": first_name(banker_name),
                       "bank": resolved[0] if resolved else bank, "event": event})
        return self._thank(profile, holds, threads, thread, "thank_you_post_event", notes, when)

    def _thank(self, profile, holds, threads, thread, key, notes, when):
        run, trace = Run("thank_you"), []
        notes = (notes or "")[:1500]
        scan = safety.scan(notes)
        trace.append({"agent": "Guard", "step": "notes scan", "detail": f"risk={scan['risk']}"})
        step = {"id": store.new_id("st"), "kind": "thank_you", "ts": iso(now()), "trace": trace, "template_key": key, "safety": {}}
        vals = {**self._values(profile, thread), "when": when, "specifics": fallback_specifics(notes)}
        try:
            self.respond(run, profile, key, vals, [], None, trace, step, own_bank=thread.get("bank"), notes=notes)
        except BudgetExceeded as e:
            step["error"] = str(e)
        step["usage"] = run.summary()
        thread["steps"].append(step)
        thread["status"] = "done" if thread.get("status") in ("scheduled", "done", "new") else thread.get("status")
        thread["updated_at"] = iso(now())
        self.save(holds, threads)
        return thread

    # ================================================================ agents
    def intake(self, run: Run, email: str, today: date, trace: list) -> dict:
        dyn = [ctx_msg({"agent": "intake", "today": today.isoformat(), "weekday": DAY_NAMES[today.weekday()]}),
               {"role": "user", "content": safety.wrap_untrusted(email)}]
        try:
            r = self.llm.call(run, "intake", prompts.INTAKE, dyn, schema=prompts.INTAKE_SCHEMA, max_output_tokens=900)
            ex = parse_json(output_text(r))
            for k, v in fallback_intake(email, today).items():
                if ex.get(k) is None:
                    ex[k] = v
            src = "agent"
        except BudgetExceeded:
            raise
        except Exception as e:  # malformed output -> deterministic fallback
            ex = fallback_intake(email, today)
            src = f"fallback ({type(e).__name__})"
        trace.append({"agent": "Intake", "step": "extracted", "detail": f"{ex.get('summary')} [{src}]", "data": ex})
        return ex

    def _tool(self, name: str, args: dict, profile, holds, mode, bank, thread_id):
        if name == "find_open_slots":
            s = date.fromisoformat(args["start_date"])
            e = date.fromisoformat(args.get("end_date") or args["start_date"])
            res = cal.find_open_slots(profile, holds, s, e, mode, bank, thread_id, args.get("earliest"), args.get("latest"),
                                      args.get("weekdays"), limit=8)
            return {"slots": [{k: v for k, v in x.items() if k in ("start", "label", "score", "trip")} for x in res], "count": len(res)}
        if name == "check_slot":
            return cal.slot_public(cal.check_slot(profile, holds, parse_dt(args["start"]), mode, bank, thread_id))
        if name == "get_trains":
            return {"trains": [trains.fmt(x) for x in trains.trains_on(date.fromisoformat(args["date"]), args.get("direction", "to_nyc"))]}
        if name == "travel_time":
            return nyc.travel(args.get("from_place"), args.get("to_place"))
        return {"error": f"unknown tool {name}"}

    def schedule(self, run, profile, ex, mode, bank, thread_id, holds, trace) -> list[dict]:
        self._availability = ex.get("banker_availability") or []
        today = now().date()
        dw = ex.get("date_window") or {}
        try:
            ws = max(date.fromisoformat(dw.get("start")), today)
            we = date.fromisoformat(dw.get("end"))
        except (TypeError, ValueError):
            ws, we = today + timedelta(days=1), today + timedelta(days=10)
        if we < ws:
            we = ws + timedelta(days=9)
        ctx = {"agent": "scheduler", "today": today.isoformat(), "weekday": DAY_NAMES[today.weekday()], "mode": mode,
               "bank": bank, "office": nyc.office_address(bank) if mode == "in_person" else None,
               "date_window": {"start": ws.isoformat(), "end": we.isoformat()},
               "banker_availability": self._availability, "purpose": ex.get("request_type")}
        dyn = [ctx_msg(ctx)]
        chosen, seen_calls = [], set()
        try:
            for _ in range(6):
                r = self.llm.call(run, "scheduler", prompts.SCHEDULER, dyn, tools=prompts.SCHEDULER_TOOLS, max_output_tokens=900)
                calls = [o for o in (r.output or []) if getattr(o, "type", "") == "function_call"]
                if not calls:
                    out = parse_json(output_text(r))
                    chosen = out.get("options", [])
                    trace.append({"agent": "Scheduler", "step": "decision", "detail": out.get("notes", ""), "data": chosen})
                    break
                dyn += list(r.output)
                for c in calls:
                    args = json.loads(c.arguments or "{}")
                    key = (c.name, json.dumps(args, sort_keys=True))
                    if key in seen_calls:
                        result = {"error": "duplicate call; you already have this result. Give your final answer now."}
                    else:
                        seen_calls.add(key)
                        try:
                            result = self._tool(c.name, args, profile, holds, mode, bank, thread_id)
                        except Exception as e:
                            result = {"error": f"{type(e).__name__}: {e}"}
                    trace.append({"agent": "Scheduler", "step": f"tool: {c.name}", "detail": json.dumps(args),
                                  "data": result if c.name != "get_trains" else {"trains": len(result.get("trains", []))}})
                    dyn.append({"type": "function_call_output", "call_id": c.call_id, "output": json.dumps(result, default=str)})
            else:
                trace.append({"agent": "Guard", "step": "loop guard", "detail": "scheduler hit 6 steps without answering; using validated fallback"})
        except BudgetExceeded:
            raise
        except Exception as e:
            trace.append({"agent": "Guard", "step": "scheduler error", "detail": f"{type(e).__name__}: {e}; using validated fallback"})
        return self.validate_options(profile, holds, chosen, mode, bank, thread_id, ws, we, trace)

    def validate_options(self, profile, holds, chosen, mode, bank, thread_id, ws, we, trace) -> list[dict]:
        """Python re-checks every time the agent proposed. The model cannot sneak in a bad time."""
        good, rejected = [], []
        for o in chosen[:3]:
            try:
                st = parse_dt(o["start"])
            except Exception:
                rejected.append({"start": o.get("start"), "reasons": ["not a valid datetime"]})
                continue
            r = cal.check_slot(profile, holds, st, mode, bank, thread_id)
            pub = cal.slot_public(r)
            if r["ok"] and not any(parse_dt(g["start"]) == st for g in good):
                pub["why"] = o.get("why", "")
                good.append(pub)
            else:
                rejected.append({"start": o.get("start"), "reasons": r.get("reasons") or ["duplicate"]})
        if rejected:
            trace.append({"agent": "Validator", "step": "rejected agent options", "detail": f"{len(rejected)} option(s) failed re-check", "data": rejected})
        if len(good) < 3:
            av = self._availability or []
            wd = sorted({a["weekday"] for a in av if a.get("weekday")}) or None
            ea = next((a["earliest"] for a in av if a.get("earliest")), None)
            la = next((a["latest"] for a in av if a.get("latest")), None)
            pool = cal.find_open_slots(profile, holds, ws, we + timedelta(days=7), mode, bank, thread_id, ea, la, wd, limit=10) if av else []
            pool += cal.find_open_slots(profile, holds, ws, we, mode, bank, thread_id, limit=10)
            if len(pool) < 6:
                pool += cal.find_open_slots(profile, holds, we + timedelta(days=1), we + timedelta(days=14), mode, bank, thread_id, limit=10)
            for p in pool:
                if len(good) >= 3:
                    break
                if not any(g["start"] == p["start"] for g in good):
                    p["why"] = "filled in by validator"
                    good.append(p)
            trace.append({"agent": "Validator", "step": "filled gaps", "detail": f"now {len(good)} validated options"})
        else:
            trace.append({"agent": "Validator", "step": "all options re-checked", "detail": "3/3 options free (classes, holds, trains, travel)"})
        good.sort(key=lambda g: g["start"])
        return good

    def respond(self, run, profile, key, values, options, confirmed, trace, step, own_bank=None, notes: str | None = None):
        templates = store.load_templates()
        ctx = {"agent": "responder", "template_key": key, "placeholder_values": values}
        if notes is not None:
            ctx["student_notes"] = notes
        dyn = [ctx_msg(ctx)]
        draft, issues = None, []
        for attempt in range(2):
            try:
                r = self.llm.call(run, "responder", prompts.responder_stable(templates), dyn, max_output_tokens=900)
                cand = parse_json(output_text(r))
                cand = {"subject": str(cand.get("subject") or "Re: Coffee Chat"), "body": str(cand.get("body", ""))}
            except BudgetExceeded:
                raise
            except Exception as e:
                issues = [f"model output unusable ({type(e).__name__})"]
                trace.append({"agent": "Responder", "step": f"draft attempt {attempt + 1}", "detail": issues[0]})
                break
            issues = safety.check_draft(cand["body"], options, profile, own_bank, confirmed, allow_text=notes or "",
                                        extra_allowed=values.get("new_banker"))
            trace.append({"agent": "Responder", "step": f"draft attempt {attempt + 1} ({key})",
                          "detail": "passed draft checker" if not issues else "checker found: " + "; ".join(issues)})
            if not issues:
                draft = cand
                break
            dyn = dyn + [{"role": "user", "content": "Your draft was rejected by the safety checker: " + "; ".join(issues)
                          + ". Rewrite it following the template and rules. Return only JSON."}]
        source = "agent"
        if draft is None:
            source = "template_fallback"
            draft = render(templates[key], values)
            trace.append({"agent": "Guard", "step": "template fallback", "detail": "agent draft failed checks; used the club template with validated values"})
        step["draft"] = draft
        step["draft_source"] = source
        step.setdefault("safety", {})["draft_issues_last"] = issues
        return draft

    # ================================================================ wellbeing
    def coach(self, use_llm: bool = True) -> dict:
        profile = store.load_profile()
        holds, threads = self.state()
        facts = wellbeing.week_facts(profile, holds, threads, store.load("checkins.json", []))
        rules = wellbeing.rule_nudges(facts)
        out = {"facts": facts, "rule_nudges": rules, "headline": "This week", "nudges": rules[:3], "source": "rules"}
        if not use_llm:
            return out
        self._allow()
        run = Run("coach")
        try:
            r = self.llm.call(run, "coach", prompts.COACH,
                              [ctx_msg({"agent": "coach", "facts": facts, "candidate_nudges": rules, "support_resource": wellbeing.YALE_SUPPORT})],
                              max_output_tokens=500)
            j = parse_json(output_text(r))
            if j.get("nudges"):
                out.update({"headline": j.get("headline", "This week"), "nudges": j["nudges"][:3], "source": "coach agent"})
        except BudgetExceeded as e:
            out["error"] = str(e)
        except Exception as e:
            out["error"] = f"coach unavailable ({type(e).__name__}); showing rule-based nudges"
        out["usage"] = run.summary()
        return out
