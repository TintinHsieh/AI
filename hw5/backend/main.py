"""FastAPI API for the Campus Customs multi-agent operations desk."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents import WorkflowResult, run_ticket
from .audit import record_event
from .db import connect, ensure_runtime_schema, reset_working_database, row_dict, rows_dict


ensure_runtime_schema()
app = FastAPI(title="Campus Customs Multi-Agent Operations API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, WorkflowResult] = {}


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=2, max_length=80)


class ResetResponse(BaseModel):
    ok: bool
    message: str
    checking_balance: float
    ticket_statuses: dict[int, str]


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def parse_event(row: dict[str, Any]) -> dict[str, Any]:
    try:
        details = json.loads(row.pop("details_json"))
    except (TypeError, json.JSONDecodeError):
        details = {"raw": row.pop("details_json", "")}
    row["details"] = details
    return row


@app.get("/api/health")
def health() -> dict[str, Any]:
    with connect(read_only=True) as connection:
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {"ok": True, "database": "campus_customs_working.db", "tables": tables, "mcp": ".mcp.json"}


@app.get("/api/tickets")
def list_tickets() -> list[dict[str, Any]]:
    with connect(read_only=True) as connection:
        return rows_dict(connection.execute("SELECT * FROM tickets ORDER BY id").fetchall())


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: int) -> dict[str, Any]:
    with connect(read_only=True) as connection:
        ticket = row_dict(connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
        if ticket is None:
            raise api_error(404, "ticket_not_found", "No ticket has that id.")
        events = rows_dict(connection.execute("SELECT * FROM audit_events WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall())
        requests = rows_dict(connection.execute("SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall())
    return {"ticket": ticket, "payment_requests": requests, "events": [parse_event(e) for e in events]}


@app.post("/api/tickets/{ticket_id}/run")
async def start_ticket_run(ticket_id: int) -> dict[str, Any]:
    with connect(read_only=True) as connection:
        exists = connection.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if exists is None:
        raise api_error(404, "ticket_not_found", "No ticket has that id.")
    result = await run_ticket(ticket_id)
    RUNS[result.run_id] = result
    return result.model_dump(mode="json")


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    result = RUNS.get(run_id)
    if result is None:
        raise api_error(404, "run_not_found", "No in-process run has that id; inspect audit events for persisted evidence.")
    return result.model_dump(mode="json")


@app.get("/api/audit")
def get_audit(ticket_id: int | None = Query(default=None), run_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    sql = "SELECT * FROM audit_events"
    clauses: list[str] = []
    args: list[Any] = []
    if ticket_id is not None:
        clauses.append("ticket_id = ?")
        args.append(ticket_id)
    if run_id:
        clauses.append("run_id = ?")
        args.append(run_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    with connect(read_only=True) as connection:
        rows = rows_dict(connection.execute(sql, args).fetchall())
    return [parse_event(row) for row in rows]


@app.get("/api/cash")
def cash_balance() -> dict[str, Any]:
    with connect(read_only=True) as connection:
        accounts = rows_dict(connection.execute("SELECT * FROM cash_accounts ORDER BY name").fetchall())
    return {"accounts": accounts, "checking": next((a for a in accounts if a["name"] == "checking"), None)}


@app.get("/api/payment-requests")
def payment_requests(status: str | None = Query(default=None)) -> list[dict[str, Any]]:
    with connect(read_only=True) as connection:
        if status:
            rows = rows_dict(connection.execute("SELECT * FROM payment_requests WHERE status = ? ORDER BY id", (status,)).fetchall())
        else:
            rows = rows_dict(connection.execute("SELECT * FROM payment_requests ORDER BY id").fetchall())
    return rows


@app.post("/api/payment-requests/{request_id}/approve")
def approve_payment(request_id: int, approval: ApprovalRequest) -> dict[str, Any]:
    approver = approval.approved_by.strip()
    if not approver:
        raise api_error(422, "invalid_approver", "approved_by is required.")
    try:
        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            request = connection.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
            if request is None:
                raise api_error(404, "payment_request_not_found", "No payment request has that id.")
            if request["status"] != "pending":
                raise api_error(409, "payment_not_pending", "Only pending payment requests can be approved.")
            ticket = connection.execute("SELECT * FROM tickets WHERE id = ?", (request["ticket_id"],)).fetchone()
            if ticket is None:
                raise api_error(409, "ticket_not_found", "The payment request references a missing ticket.")
            if request["kind"] == "invoice":
                obligation = connection.execute("SELECT * FROM invoices WHERE id = ?", (request["ref_id"],)).fetchone()
                if obligation is None or obligation["status"] not in ("open", "due") or ticket["invoice_id"] != request["ref_id"]:
                    raise api_error(409, "invalid_obligation", "The payment request is not tied to an open invoice for its ticket.")
                if float(request["amount"]) != float(obligation["amount"]):
                    raise api_error(409, "invalid_amount", "The payment request amount does not match the invoice obligation.")
            elif request["kind"] == "lease":
                obligation = connection.execute("SELECT * FROM leases WHERE id = ?", (request["ref_id"],)).fetchone()
                if obligation is None or ticket["lease_id"] != request["ref_id"]:
                    raise api_error(409, "invalid_obligation", "The payment request is not tied to a lease for its ticket.")
                if float(request["amount"]) != float(obligation["monthly_rent"]):
                    raise api_error(409, "invalid_amount", "The payment request amount does not match the lease obligation.")
            else:
                raise api_error(409, "invalid_payment_kind", "The payment request kind is not approved by policy.")
            duplicate = connection.execute("SELECT 1 FROM payments WHERE kind = ? AND ref_id = ? AND account = ?", (request["kind"], request["ref_id"], request["account"])).fetchone()
            if duplicate is not None:
                raise api_error(409, "duplicate_payment", "A payment for this obligation and account already exists.")
            account = connection.execute("SELECT * FROM cash_accounts WHERE name = ?", (request["account"],)).fetchone()
            if account is None:
                raise api_error(409, "account_not_found", "The payment account does not exist.")
            if float(account["balance"]) < float(request["amount"]):
                raise api_error(409, "insufficient_funds", "Approving this payment would make checking negative.")
            paid_at = datetime.now(timezone.utc).isoformat()
            cursor = connection.execute("INSERT INTO payments(kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)", (request["kind"], request["ref_id"], request["amount"], request["account"], paid_at, approver))
            payment_id = int(cursor.lastrowid)
            connection.execute("UPDATE cash_accounts SET balance = balance - ? WHERE name = ?", (request["amount"], request["account"]))
            if request["kind"] == "invoice":
                connection.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (request["ref_id"],))
            connection.execute("UPDATE payment_requests SET status='approved', approved_by=?, approved_at=?, executed_payment_id=? WHERE id=?", (approver, paid_at, payment_id, request_id))
            connection.execute("UPDATE tickets SET status='resolved' WHERE id = ?", (request["ticket_id"],))
            connection.commit()
            result = row_dict(connection.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone())
            balance = row_dict(connection.execute("SELECT * FROM cash_accounts WHERE name = ?", (request["account"],)).fetchone())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise api_error(500, "approval_failed", str(exc)) from exc
    record_event(run_id=f"approval-{request_id}", ticket_id=result["ticket_id"], agent="Human Approval", event_type="payment_executed", details={"request_id": request_id, "payment_id": payment_id, "approved_by": approver, "amount": result["amount"]})
    return {"payment_request": result, "payment_id": payment_id, "cash_account": balance}


@app.post("/api/reset", response_model=ResetResponse)
def reset() -> ResetResponse:
    reset_working_database()
    with connect(read_only=True) as connection:
        balance = float(connection.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0])
        statuses = {int(row["id"]): row["status"] for row in connection.execute("SELECT id, status FROM tickets ORDER BY id")}
    record_event(run_id=f"reset-{uuid.uuid4().hex}", agent="System", event_type="database_reset", details={"checking_balance": balance, "ticket_statuses": statuses})
    return ResetResponse(ok=True, message="Working database restored from the protected original.", checking_balance=balance, ticket_statuses=statuses)

