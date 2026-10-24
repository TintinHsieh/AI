"""LLM wrapper: OpenAI Responses API through Portkey (or OpenAI directly).

Every call goes through LLM.call(), which
  * enforces budgets (calls per run, tokens per run, tokens per day)
  * puts the long, unchanging agent playbook first with an explicit cache breakpoint
  * records input / cached / cache-write / output tokens and $ cost for the Usage tab
"""
import json
import time
from dataclasses import dataclass, field
from datetime import datetime

from . import config, store
from .tools.timeutil import now


class BudgetExceeded(Exception):
    pass


@dataclass
class Run:
    kind: str
    calls: list = field(default_factory=list)
    started: float = field(default_factory=time.time)

    @property
    def tokens(self) -> int:
        return sum(c["input_tokens"] + c["output_tokens"] for c in self.calls)

    @property
    def cost(self) -> float:
        return sum(c["cost_usd"] for c in self.calls)

    def summary(self) -> dict:
        keys = ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens")
        tot = {k: sum(c[k] for c in self.calls) for k in keys}
        return {**tot, "llm_calls": len(self.calls), "cost_usd": round(self.cost, 6),
                "seconds": round(time.time() - self.started, 2), "by_agent": self.calls}


def price(model: str, inp: int, cached: int, write: int, out: int) -> float:
    p = config.PRICES.get(model, config.PRICES[config.COURSE_MODEL])
    fresh = max(0, inp - cached - write)
    return (fresh * p["input"] + cached * p["cached"] + write * p["cache_write"] + out * p["output"]) / 1e6


def tokens_today() -> int:
    today = now().date().isoformat()
    return sum(r.get("input_tokens", 0) + r.get("output_tokens", 0)
               for r in store.read_jsonl("usage.jsonl") if r.get("ts", "").startswith(today))


class LLM:
    def __init__(self, settings: config.Settings | None = None):
        self.s = settings or config.load_settings()
        self.optional_ok = True   # cache options + reasoning effort; dropped if the gateway rejects them
        self.schema_ok = True
        if self.s.provider == "mock":
            from .mock_llm import MockBackend
            self.client = MockBackend()
        else:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.s.api_key, base_url=self.s.base_url, timeout=60, max_retries=2)

    @property
    def mode(self) -> str:
        return self.s.provider

    def _guard(self, run: Run):
        if len(run.calls) >= self.s.max_llm_calls_per_run:
            raise BudgetExceeded(f"stopped: more than {self.s.max_llm_calls_per_run} model calls in one run (loop guard)")
        if run.tokens >= self.s.run_token_budget:
            raise BudgetExceeded(f"stopped: run used {run.tokens} tokens (cap {self.s.run_token_budget})")
        if tokens_today() >= self.s.daily_token_budget:
            raise BudgetExceeded(f"daily token budget of {self.s.daily_token_budget} reached; try again tomorrow")

    def call(self, run: Run, agent: str, stable: str, dynamic: list, tools: list | None = None,
             schema: dict | None = None, max_output_tokens: int = 1200):
        self._guard(run)
        t0 = time.time()
        for _ in range(3):
            stable_part = {"type": "input_text", "text": stable}
            if self.optional_ok and self.s.use_cache:
                stable_part["prompt_cache_breakpoint"] = {"mode": "explicit"}
            kw = {"model": self.s.model, "input": [{"role": "developer", "content": [stable_part]}] + dynamic,
                  "max_output_tokens": max_output_tokens}
            if tools:
                kw["tools"] = tools
            if schema and self.schema_ok:
                kw["text"] = {"format": {"type": "json_schema", "name": schema["name"],
                                         "schema": schema["schema"], "strict": False}}
            if self.optional_ok and self.s.use_cache:
                kw["extra_body"] = {"prompt_cache_options": {"mode": "explicit", "ttl": "30m"}}
            if self.optional_ok:
                kw["reasoning"] = {"effort": self.s.reasoning_effort}
            try:
                r = self.client.responses.create(**kw)
                return self._finish(run, agent, r, t0)
            except Exception as e:
                # The gateway may reject an optional feature: drop it and retry.
                if not self._is_bad_request(e):
                    raise
                if self.optional_ok:
                    self.optional_ok = False
                elif "text" in kw:
                    self.schema_ok = False
                else:
                    raise
        raise RuntimeError("model call failed")

    @staticmethod
    def _is_bad_request(e: Exception) -> bool:
        # 400 from the gateway, or an older SDK refusing an unknown argument
        return getattr(e, "status_code", None) in (400, 422) or type(e).__name__ in ("BadRequestError", "TypeError", "UnprocessableEntityError")

    def _finish(self, run: Run, agent: str, r, t0: float):
        u = getattr(r, "usage", None)
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        d = getattr(u, "input_tokens_details", None)
        cached = getattr(d, "cached_tokens", 0) or 0
        write = getattr(d, "cache_write_tokens", 0) or 0
        od = getattr(u, "output_tokens_details", None)
        reasoning = getattr(od, "reasoning_tokens", 0) or 0
        rec = {
            "ts": now().isoformat(timespec="seconds"), "run": run.kind, "agent": agent, "model": self.s.model,
            "provider": self.s.provider, "input_tokens": inp, "cached_tokens": cached, "cache_write_tokens": write,
            "output_tokens": out, "reasoning_tokens": reasoning,
            "cost_usd": round(price(self.s.model, inp, cached, write, out), 7),
            "latency_ms": int((time.time() - t0) * 1000),
        }
        run.calls.append(rec)
        store.append_jsonl("usage.jsonl", rec)
        return r


def output_text(r) -> str:
    t = getattr(r, "output_text", None)
    if t:
        return t
    parts = []
    for item in getattr(r, "output", []) or []:
        if getattr(item, "type", "") == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "text", None):
                    parts.append(c.text)
    return "".join(parts)


def parse_json(text: str) -> dict:
    """Parse a JSON object even if the model wrapped it in prose or ``` fences."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        try:
            return json.loads(text[a:b + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("model did not return valid JSON")
