"""Offline stand-in for the model (DEMO MODE, used when no API key is set, and in tests).

It mimics the Responses API shape (output items, function calls, usage) so the exact same
pipeline code runs. Token counts are estimated (chars / 4) and labeled provider="mock".
"""
import json
from datetime import date
from types import SimpleNamespace as NS

from . import agents
from .tools.timeutil import parse_dt


def _text_of(item) -> str:
    if isinstance(item, dict):
        c = item.get("content") or item.get("output") or ""
        if isinstance(c, list):
            return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
        return str(c)
    return str(getattr(item, "arguments", "") or "")


class _Responses:
    def __init__(self):
        self.cache: set[str] = set()

    def create(self, **kw):
        inp = kw["input"]
        stable = inp[0]["content"][0]["text"]
        ctx = {}
        for it in inp:
            t = _text_of(it)
            if isinstance(it, dict) and t.startswith("CONTEXT_JSON:"):
                ctx = json.loads(t.split("\n", 1)[1])
        agent = ctx.get("agent")
        if agent == "intake":
            email = next(_text_of(i) for i in inp if isinstance(i, dict) and i.get("role") == "user" and "<banker_email>" in _text_of(i))
            email = email.split("<banker_email>\n", 1)[1].split("\n</banker_email>")[0]
            out = self._msg(json.dumps(agents.fallback_intake(email, date.fromisoformat(ctx["today"]))))
        elif agent == "scheduler":
            tool_outputs = [i for i in inp if isinstance(i, dict) and i.get("type") == "function_call_output"]
            if not tool_outputs:
                args = {"start_date": ctx["date_window"]["start"], "end_date": ctx["date_window"]["end"]}
                av = ctx.get("banker_availability") or []
                days = sorted({a["weekday"] for a in av if a.get("weekday")})
                if days:
                    args["weekdays"] = days
                if av and av[0].get("earliest"):
                    args["earliest"] = av[0]["earliest"]
                if av and av[0].get("latest"):
                    args["latest"] = av[0]["latest"]
                out = [NS(type="function_call", name="find_open_slots", arguments=json.dumps(args), call_id="call_1")]
            else:
                slots = json.loads(tool_outputs[-1]["output"]).get("slots", [])
                days, pick = set(), []
                for s in slots:
                    d = parse_dt(s["start"]).date()
                    if d not in days:
                        days.add(d)
                        pick.append(s)
                    if len(pick) == 3:
                        break
                for s in slots:
                    if len(pick) < 3 and s not in pick:
                        pick.append(s)
                out = self._msg(json.dumps({"options": [{"start": s["start"], "why": "high score, different day"} for s in pick],
                                            "notes": "Picked the top-scored windows on different days."}))
        elif agent == "responder":
            out = self._msg(json.dumps(self._draft(ctx, stable)))
        elif agent == "coach":
            nudges = ctx["candidate_nudges"][:3]
            out = self._msg(json.dumps({"headline": "Pace yourself this week", "nudges": nudges}))
        else:
            out = self._msg("{}")
        n_in = sum(len(_text_of(i)) for i in inp) // 4 + len(stable) // 4 + len(json.dumps(kw.get("tools") or [])) // 4
        stable_tok = len(stable) // 4
        cached = stable_tok if (stable in self.cache and stable_tok >= 1024) else 0
        write = stable_tok if (stable not in self.cache and stable_tok >= 1024) else 0
        self.cache.add(stable)
        n_out = sum(len(getattr(o, "arguments", "") or getattr(o, "_text", "")) for o in out) // 4 + 5
        text = "".join(getattr(o, "_text", "") for o in out)
        usage = NS(input_tokens=n_in, output_tokens=n_out, input_tokens_details=NS(cached_tokens=cached, cache_write_tokens=write),
                   output_tokens_details=NS(reasoning_tokens=0))
        return NS(output=out, output_text=text, usage=usage)

    @staticmethod
    def _msg(text: str):
        return [NS(type="message", _text=text, content=[NS(type="output_text", text=text)])]

    @staticmethod
    def _draft(ctx: dict, stable: str) -> dict:
        from . import store
        vals = dict(ctx["placeholder_values"])
        if ctx.get("student_notes") is not None:
            vals["specifics"] = agents.fallback_specifics(ctx["student_notes"])
        return agents.render(store.load_templates()[ctx["template_key"]], vals)


class MockBackend:
    def __init__(self):
        self.responses = _Responses()
