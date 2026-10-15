"""Offline FastAPI smoke evidence using a temporary copy of the supplied database.

This test deliberately does not call the model. It covers the API contract and
financial safety paths without changing the preserved HW5 working database.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


PROJECT_DIR = Path(__file__).resolve().parents[1]
ORIGINAL_DB = PROJECT_DIR / "data" / "campus_customs_original.db"
OUTPUT = PROJECT_DIR / "output" / "backend_smoke.json"
sys.path.insert(0, str(PROJECT_DIR))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(checks: list[dict[str, Any]], name: str, response: Any, expected: Any) -> None:
    actual = response.json()
    passed = response.status_code == expected["status_code"] and expected.get("predicate", lambda _: True)(actual)
    checks.append({
        "check": name,
        "status_code": response.status_code,
        "returned": actual,
        "expected_status_code": expected["status_code"],
        "passed": passed,
    })


def run() -> dict[str, Any]:
    original_hash_before = sha256(ORIGINAL_DB)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="hw5-backend-smoke-") as temp_dir:
        working_db = Path(temp_dir) / "campus_customs_working.db"
        shutil.copy2(ORIGINAL_DB, working_db)

        # Patch only the imported database module; all API code still uses its
        # production connection, schema, transaction, and route logic.
        from backend import db

        db.WORKING_DB = working_db
        db.ORIGINAL_DB = ORIGINAL_DB
        from backend.main import app

        with TestClient(app) as client:
            record(checks, "health", client.get("/api/health"), {
                "status_code": 200,
                "predicate": lambda body: body["ok"] and "tickets" in body["tables"],
            })
            record(checks, "list_tickets", client.get("/api/tickets"), {
                "status_code": 200,
                "predicate": lambda body: [row["id"] for row in body] == [101, 102, 103],
            })
            record(checks, "ticket_detail", client.get("/api/tickets/101"), {
                "status_code": 200,
                "predicate": lambda body: body["ticket"]["status"] == "open",
            })
            record(checks, "invalid_ticket_detail", client.get("/api/tickets/999"), {
                "status_code": 404,
                "predicate": lambda body: body["detail"]["code"] == "ticket_not_found",
            })
            record(checks, "invalid_ticket_run_guard", client.post("/api/tickets/999/run"), {
                "status_code": 404,
                "predicate": lambda body: body["detail"]["code"] == "ticket_not_found",
            })
            record(checks, "initial_cash", client.get("/api/cash"), {
                "status_code": 200,
                "predicate": lambda body: body["checking"]["balance"] == 3400.0,
            })

            with closing(sqlite3.connect(working_db)) as connection:
                connection.execute(
                    "INSERT INTO payment_requests(ticket_id, kind, ref_id, amount, account, reason, status, requested_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (102, "lease", 1, 2400.0, "checking", "Test lease approval", "pending", "Smoke Test"),
                )
                connection.commit()
            record(checks, "pending_request_listing", client.get("/api/payment-requests?status=pending"), {
                "status_code": 200,
                "predicate": lambda body: len(body) == 1 and body[0]["amount"] == 2400.0,
            })
            approved = client.post("/api/payment-requests/1/approve", json={"approved_by": "Smoke Tester"})
            record(checks, "approval_success", approved, {
                "status_code": 200,
                "predicate": lambda body: body["cash_account"]["balance"] == 1000.0 and body["payment_request"]["status"] == "approved",
            })
            record(checks, "duplicate_approval", client.post("/api/payment-requests/1/approve", json={"approved_by": "Smoke Tester"}), {
                "status_code": 409,
                "predicate": lambda body: body["detail"]["code"] == "payment_not_pending",
            })

            with closing(sqlite3.connect(working_db)) as connection:
                connection.execute("UPDATE cash_accounts SET balance = 500 WHERE name = 'checking'")
                connection.execute(
                    "INSERT INTO payment_requests(ticket_id, kind, ref_id, amount, account, reason, status, requested_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (101, "invoice", 501, 840.0, "checking", "Test insufficient funds", "pending", "Smoke Test"),
                )
                connection.commit()
            record(checks, "insufficient_funds", client.post("/api/payment-requests/2/approve", json={"approved_by": "Smoke Tester"}), {
                "status_code": 409,
                "predicate": lambda body: body["detail"]["code"] == "insufficient_funds",
            })

            reset = client.post("/api/reset")
            record(checks, "reset_working_database", reset, {
                "status_code": 200,
                "predicate": lambda body: body["checking_balance"] == 3400.0 and body["ticket_statuses"] == {"101": "open", "102": "open", "103": "open"},
            })
            with closing(sqlite3.connect(working_db)) as connection:
                payment_count = connection.execute("SELECT count(*) FROM payments").fetchone()[0]
                pending_count = connection.execute("SELECT count(*) FROM payment_requests").fetchone()[0]
            checks.append({
                "check": "post_reset_financial_state",
                "returned": {"payments": payment_count, "payment_requests": pending_count},
                "expected": {"payments": 0, "payment_requests": 0},
                "passed": payment_count == 0 and pending_count == 0,
            })

    original_hash_after = sha256(ORIGINAL_DB)
    evidence = {
        "schema_version": "hw5.problem11.backend_smoke.v1",
        "status": "passed" if all(item["passed"] for item in checks) and original_hash_before == original_hash_after else "failed",
        "uses_temporary_database": True,
        "model_calls_made": False,
        "checks": checks,
        "original_sha256_before": original_hash_before,
        "original_sha256_after": original_hash_after,
        "original_unchanged": original_hash_before == original_hash_after,
    }
    OUTPUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
