"""End-to-end through the HTTP API in demo mode."""
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def email(name):
    return open(f"data/sample_emails/{name}.txt", encoding="utf-8").read()


def test_status_and_samples():
    assert c.get("/api/status").json()["demo_mode"] is True
    assert len(c.get("/api/samples").json()) >= 6


def test_outreach_reply_invite_flow():
    th = c.post("/api/outreach", json={"banker_name": "Priya Raman", "bank": "Goldman Sachs", "event": "Goldman Sachs Corporate Presentation",
                                       "referrer": "Henry Liu", "mode": "either"}).json()
    st = th["steps"][-1]
    assert st["template_key"] == "outreach_intro" and len(st["options"]) == 3
    assert "Henry Liu shared your contact information" in st["draft"]["body"]
    assert len([h for h in c.get("/api/holds").json() if h["thread_id"] == th["id"]]) == 3
    th = c.post(f"/api/threads/{th['id']}/steps/{st['id']}/sent").json()
    assert th["status"] == "awaiting_banker" and th["follow_up_due"]
    o = datetime.fromisoformat(st["options"][0]["start"])
    reply = f"Hi,\n{o.strftime('%A')} {o.month}/{o.day} at {o.strftime('%I:%M %p').lstrip('0')} works great for me.\n\nBest,\nPriya Raman\nGoldman Sachs"
    th = c.post("/api/inbox", json={"email": reply, "thread_id": th["id"]}).json()
    inv = th["steps"][-1]
    assert inv["template_key"] in ("invite_virtual", "invite_in_person") and inv["matched_hold"]
    th = c.post(f"/api/threads/{th['id']}/steps/{inv['id']}/sent").json()
    assert th["status"] == "scheduled"
    mine = [h for h in c.get("/api/holds").json() if h["thread_id"] == th["id"]]
    assert [h["status"] for h in mine] == ["confirmed"]
    ics = c.get(f"/api/ics/{mine[0]['id']}")
    assert "BEGIN:VEVENT" in ics.text


def test_injection_email_flagged_and_reply_is_clean():
    th = c.post("/api/inbox", json={"email": email("05_injection_attack")}).json()
    st = th["steps"][-1]
    assert th["suspicious"] and st["extracted"]["suspicious"]
    body = st["draft"]["body"]
    for bad in ("Accounting", "Competitor", "PORTKEY", "system prompt", "Goldman"):
        assert bad not in body


def test_intro_suggests_outreach():
    th = c.post("/api/inbox", json={"email": email("07_intro")}).json()
    st = th["steps"][-1]
    assert st["template_key"] == "thank_you_for_intro"
    assert st["suggested_outreach"]["banker_name"] == "Maria Gonzalez"
    assert "Maria Gonzalez" in st["draft"]["body"]


def test_running_late_uses_no_tokens():
    th = c.post("/api/inbox", json={"email": email("03_lazard_in_person")}).json()
    th = c.post(f"/api/threads/{th['id']}/late", json={"location": "lobby at 30 Rockefeller Plaza"}).json()
    st = th["steps"][-1]
    assert "lobby at 30 Rockefeller Plaza" in st["draft"]["body"] and st["usage"]["llm_calls"] == 0


def test_usage_and_coach():
    c.post("/api/inbox", json={"email": email("01_evercore_virtual")})
    u = c.get("/api/usage").json()
    assert u["inbox_runs"] >= 1 and u["avg_inbox_run"]["llm_calls"] >= 3
    co = c.post("/api/coach", json={"use_llm": True}).json()
    assert co["nudges"]
