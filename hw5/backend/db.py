"""Database paths, read-only reads, and safe working-database operations."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
WORKING_DB = DATA_DIR / "campus_customs_working.db"
ORIGINAL_DB = DATA_DIR / "campus_customs_original.db"


RUNTIME_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    ref_id INTEGER,
    amount REAL NOT NULL CHECK (amount > 0),
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    approved_by TEXT,
    approved_at TEXT,
    executed_payment_id INTEGER,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    UNIQUE (ticket_id, kind, ref_id, status)
);
CREATE INDEX IF NOT EXISTS idx_payment_requests_ticket ON payment_requests(ticket_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_status ON payment_requests(status);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    ticket_id INTEGER,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
CREATE INDEX IF NOT EXISTS idx_audit_events_run ON audit_events(run_id, id);
CREATE INDEX IF NOT EXISTS idx_audit_events_ticket ON audit_events(ticket_id, id);
"""


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback and close when used in a ``with connect()`` block."""

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(*, read_only: bool = False) -> sqlite3.Connection:
    """Open the fixed working database with safe connection settings."""

    if read_only:
        connection = sqlite3.connect(f"{WORKING_DB.resolve().as_uri()}?mode=ro", uri=True, timeout=5, factory=ClosingConnection)
    else:
        connection = sqlite3.connect(WORKING_DB, timeout=5, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if read_only:
        connection.execute("PRAGMA query_only = ON")
    return connection


def ensure_runtime_schema() -> None:
    """Add only app-owned audit/request tables to the working copy."""

    if not WORKING_DB.exists():
        raise FileNotFoundError(WORKING_DB)
    with connect() as connection:
        connection.executescript(RUNTIME_SCHEMA)


def reset_working_database() -> None:
    """Restore the working copy from the protected original, then migrate runtime tables."""

    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(ORIGINAL_DB)
    WORKING_DB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ORIGINAL_DB, WORKING_DB)
    ensure_runtime_schema()


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_dict(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]

