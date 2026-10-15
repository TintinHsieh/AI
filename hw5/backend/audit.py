"""Persistent, privacy-conscious workflow audit events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import connect


def record_event(
    *,
    run_id: str,
    agent: str,
    event_type: str,
    details: dict[str, Any],
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Write one bounded observable event to the working database."""

    safe_details = json.loads(json.dumps(details, default=str))
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO audit_events(run_id, ticket_id, agent, event_type, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, ticket_id, agent, event_type, json.dumps(safe_details, sort_keys=True)),
        )
        event_id = int(cursor.lastrowid)
    return {"id": event_id, "run_id": run_id, "ticket_id": ticket_id, "agent": agent, "event_type": event_type, "details": safe_details}

