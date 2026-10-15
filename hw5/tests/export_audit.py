"""Export the preserved operational audit trail without changing the database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "data" / "campus_customs_working.db"
OUTPUT = PROJECT_DIR / "output" / "audit_trail.json"


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    connection = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    events = rows(connection, "audit_events")
    for event in events:
        try:
            event["details"] = json.loads(event.pop("details_json"))
        except (TypeError, json.JSONDecodeError):
            event["details"] = {"raw": event.pop("details_json", "")}
    evidence = {
        "schema_version": "hw5.problem9.audit_trail.v1",
        "database": "data/campus_customs_working.db",
        "protected_original": "data/campus_customs_original.db",
        "working_sha256": sha256(DB_PATH),
        "tickets": rows(connection, "tickets"),
        "cash_accounts": rows(connection, "cash_accounts"),
        "payments": rows(connection, "payments"),
        "payment_requests": rows(connection, "payment_requests"),
        "audit_events": events,
        "event_count": len(events),
        "payment_count": len(rows(connection, "payments")),
        "pending_payment_count": sum(1 for item in rows(connection, "payment_requests") if item["status"] == "pending"),
        "note": "Exported read-only from the preserved working database; no payment approval was performed.",
    }
    connection.close()
    OUTPUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "event_count": evidence["event_count"], "payment_count": evidence["payment_count"], "pending_payment_count": evidence["pending_payment_count"]}, indent=2))


if __name__ == "__main__":
    main()
