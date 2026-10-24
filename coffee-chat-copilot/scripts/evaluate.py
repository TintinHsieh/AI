"""Measure real token usage, cost, latency, and quality on the sample emails.

  python scripts/evaluate.py                      # default settings (reasoning effort low, cache on)
  python scripts/evaluate.py --effort medium      # compare: does spending more help?
  python scripts/evaluate.py --no-cache           # compare: what does prompt caching save?

Writes docs/evidence/eval_<label>.json and .md. Uses a throwaway state folder so your real data is untouched.
Quality checks per email (no human judgment needed):
  * intake fields correct vs data/sample_emails/expected.json (bank, mode, request type, suspicious, intro name)
  * banker's availability respected (weekday / earliest / latest) for every offered window
  * scheduler options accepted by the validator without replacement
  * responder draft passed the safety checker on the first try (no template fallback)
"""
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--effort", default="low")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--label", default=None)
    ap.add_argument("--repeat", type=int, default=1, help="run the whole suite N times (shows caching on later runs)")
    a = ap.parse_args()
    os.environ["REASONING_EFFORT"] = a.effort
    os.environ["USE_PROMPT_CACHE"] = "0" if a.no_cache else "1"
    os.environ["COPILOT_STATE_DIR"] = tempfile.mkdtemp(prefix="ccc_eval_")
    os.environ["MAX_RUNS_PER_MINUTE"] = "1000"
    from app import config
    config.STATE_DIR = Path(os.environ["COPILOT_STATE_DIR"])
    from app.agents import Copilot
    from app.tools.timeutil import parse_dt
    cp = Copilot()
    if cp.llm.mode == "mock":
        print("WARNING: no API key found, running in DEMO mode (token counts are estimates).")
    label = a.label or f"{cp.llm.mode}_{a.effort}{'_nocache' if a.no_cache else ''}"
    expected = json.loads((ROOT / "data/sample_emails/expected.json").read_text(encoding="utf-8"))
    rows = []
    for rep in range(a.repeat):
        # an outreach first so the confirmation email has holds to match
        th = cp.compose_outreach("Daniel Park", "Evercore", "Evercore Corporate Presentation", None, "virtual")
        st = th["steps"][-1]
        rows.append(row("outreach", st, {}, None, rep))
        for name, exp in expected.items():
            text = (ROOT / f"data/sample_emails/{name}.txt").read_text(encoding="utf-8")
            if name == "06_evercore_confirm":  # confirm the first window we actually offered
                o = parse_dt(st["options"][0]["start"])
                text = text.replace("Thursday at 12:00 PM", f"{o.strftime('%A')} {o.month}/{o.day} at {o.strftime('%I:%M %p').lstrip('0')}")
            t0 = time.time()
            th2 = cp.process_email(text)
            rows.append(row(name, th2["steps"][-1], exp, time.time() - t0, rep))
        th3 = cp.thank_you(th["id"], "his move from consulting into restructuring; advice to know the 3-statement model cold")
        rows.append(row("thank_you", th3["steps"][-1], {}, None, rep))
    summary = summarize(rows, cp.llm.mode, a)
    out = ROOT / "docs" / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"eval_{label}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, default=str), encoding="utf-8")
    (out / f"eval_{label}.md").write_text(markdown(summary, rows, label), encoding="utf-8")
    print(markdown(summary, rows, label))
    print(f"\nSaved to docs/evidence/eval_{label}.md")


def row(name, st, exp, secs, rep):
    from app.tools.timeutil import parse_dt
    ex = st.get("extracted") or {}
    u = st.get("usage", {})
    checks = {}
    for k in ("bank", "mode", "request_type", "suspicious", "introduced_name"):
        if k in exp:
            got = ex.get(k)
            if k == "bank":
                from app.tools import nyc
                got = (nyc.resolve_bank(got) or (got,))[0]
            checks[f"intake_{k}"] = (got == exp[k]) or (k == "mode" and exp[k] == "phone" and got in ("phone", "virtual"))
    opts = st.get("options") or []
    if opts and ("weekdays" in exp or "earliest" in exp or "latest" in exp):
        ok = True
        for o in opts:
            s, e = parse_dt(o["start"]), parse_dt(o["end"])
            if "weekdays" in exp and s.strftime("%a") not in exp["weekdays"]:
                ok = False
            if "earliest" in exp and s.strftime("%H:%M") < exp["earliest"]:
                ok = False
            if "latest" in exp and e.strftime("%H:%M") > exp["latest"]:
                ok = False
        checks["banker_window_respected"] = ok
    trace = st.get("trace", [])
    if opts:
        checks["validator_no_rejections"] = not any(t["step"] == "rejected agent options" for t in trace)
        checks["no_gap_filling"] = not any(t["step"] == "filled gaps" for t in trace)
    if st.get("draft"):
        checks["draft_first_try"] = st.get("draft_source") == "agent" and not any("attempt 2" in t["step"] for t in trace)
    return {"rep": rep, "email": name, "template": st.get("template_key"), "llm_calls": u.get("llm_calls", 0),
            "input": u.get("input_tokens", 0), "cached": u.get("cached_tokens", 0), "cache_write": u.get("cache_write_tokens", 0),
            "output": u.get("output_tokens", 0), "reasoning": u.get("reasoning_tokens", 0), "cost_usd": u.get("cost_usd", 0),
            "seconds": round(secs if secs is not None else u.get("seconds", 0), 2), "checks": checks,
            "tool_calls": [t["detail"] for t in trace if t["step"].startswith("tool:")]}


def summarize(rows, mode, a):
    inbound = [r for r in rows if r["email"] not in ("outreach", "thank_you")]
    allchecks = [v for r in rows for v in r["checks"].values()]
    n = len(inbound) or 1
    return {"provider": mode, "effort": a.effort, "cache": not a.no_cache, "when": datetime.now().isoformat(timespec="seconds"),
            "emails": len(inbound), "avg_input": round(sum(r["input"] for r in inbound) / n), "avg_cached": round(sum(r["cached"] for r in inbound) / n),
            "avg_output": round(sum(r["output"] for r in inbound) / n), "avg_calls": round(sum(r["llm_calls"] for r in inbound) / n, 2),
            "avg_cost_usd": round(sum(r["cost_usd"] for r in inbound) / n, 6), "avg_seconds": round(sum(r["seconds"] for r in inbound) / n, 2),
            "max_seconds": max((r["seconds"] for r in inbound), default=0),
            "cache_hit_rate": round(sum(r["cached"] for r in rows) / max(1, sum(r["input"] for r in rows)), 3),
            "quality_checks_passed": f"{sum(allchecks)}/{len(allchecks)}", "quality_pct": round(100 * sum(allchecks) / max(1, len(allchecks)), 1),
            "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 6)}


def markdown(s, rows, label):
    out = [f"# Evaluation: {label}", "", f"Run {s['when']} · provider **{s['provider']}** · reasoning effort **{s['effort']}** · prompt cache **{'on' if s['cache'] else 'off'}**", "",
           "| Metric | Value |", "|---|---|"]
    for k in ("emails", "avg_calls", "avg_input", "avg_cached", "avg_output", "avg_cost_usd", "avg_seconds", "max_seconds", "cache_hit_rate", "quality_checks_passed", "total_cost_usd"):
        out.append(f"| {k} | {s[k]} |")
    out += ["", "| # | Email | Template | Calls | Input | Cached | Output | Cost ($) | Sec | Checks |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        chk = ", ".join(f"{k}:{'✔' if v else '✘'}" for k, v in r["checks"].items())
        out.append(f"| {r['rep']} | {r['email']} | {r['template']} | {r['llm_calls']} | {r['input']} | {r['cached']} | {r['output']} | {r['cost_usd']:.6f} | {r['seconds']} | {chk} |")
    return "\n".join(out)


if __name__ == "__main__":
    main()
