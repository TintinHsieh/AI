"""FastMCP server for the Campus Customs operational database."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from backend.db import connect, ensure_runtime_schema, row_dict, rows_dict


PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = (PROJECT_DIR / "data" / "campus_customs_working.db").resolve()
TICKET_ID_PATTERN = re.compile(r"^[0-9]{1,9}$")
SKU_PATTERN = re.compile(r"^[A-Z0-9-]{2,40}$")

mcp = FastMCP(
    name="Campus Customs Operations",
    instructions=(
        "Use bounded business tools for Tickets 101, 102, and 103. "
        "The server reads the HW5 working database. Payment preparation is "
        "allowed only through its narrow request tool; actual payment execution "
        "requires the separate human-approval API."
    ),
)


class ToolError(BaseModel):
    code: str
    message: str


class ToolEnvelope(BaseModel):
    ok: bool
    error: ToolError | None = None


class TicketResult(ToolEnvelope):
    ticket: dict[str, Any] | None = None
    related: dict[str, Any] = Field(default_factory=dict)


class InventoryResult(ToolEnvelope):
    sku: str
    size: str | None = None
    inventory: list[dict[str, Any]] = Field(default_factory=list)
    pricing: dict[str, Any] | None = None


class ObligationResult(ToolEnvelope):
    ticket_id: int
    obligation: dict[str, Any] | None = None
    cash_accounts: list[dict[str, Any]] = Field(default_factory=list)
    existing_payments: list[dict[str, Any]] = Field(default_factory=list)
    payment_requests: list[dict[str, Any]] = Field(default_factory=list)


class CashResult(ToolEnvelope):
    account: str
    accounts: list[dict[str, Any]] = Field(default_factory=list)


class PaymentRequestResult(ToolEnvelope):
    request: dict[str, Any] | None = None


def err(code: str, message: str) -> ToolError:
    return ToolError(code=code, message=message)


def valid_ticket_id(ticket_id: int) -> bool:
    return isinstance(ticket_id, int) and not isinstance(ticket_id, bool) and bool(TICKET_ID_PATTERN.fullmatch(str(ticket_id)))


def valid_sku(sku: str) -> bool:
    return isinstance(sku, str) and bool(SKU_PATTERN.fullmatch(sku.strip().upper()))


def ticket_bundle(connection: sqlite3.Connection, ticket_id: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    ticket = row_dict(connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
    if ticket is None:
        return None, {}
    related: dict[str, Any] = {}
    if ticket.get("sku"):
        related["inventory"] = rows_dict(connection.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY size", (ticket["sku"],)).fetchall())
        related["pricing"] = row_dict(connection.execute("SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone())
    if ticket.get("invoice_id"):
        related["invoice"] = row_dict(connection.execute("""
            SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days
            FROM invoices AS i JOIN vendors AS v ON v.id = i.vendor_id WHERE i.id = ?
        """, (ticket["invoice_id"],)).fetchone())
    if ticket.get("lease_id"):
        related["lease"] = row_dict(connection.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone())
    related["cash_accounts"] = rows_dict(connection.execute("SELECT * FROM cash_accounts ORDER BY name").fetchall())
    related["payments"] = rows_dict(connection.execute(
        "SELECT * FROM payments WHERE ref_id = ? ORDER BY id",
        (ticket.get("invoice_id") or ticket.get("lease_id"),),
    ).fetchall())
    related["payment_requests"] = rows_dict(connection.execute("SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall())
    return ticket, related


@mcp.tool(name="inspect_ticket", description="Inspect one operational ticket and related inventory, pricing, invoice, lease, cash, payment, and request evidence.")
def inspect_ticket(ticket_id: int) -> TicketResult:
    if not valid_ticket_id(ticket_id):
        return TicketResult(ok=False, error=err("invalid_ticket_id", "ticket_id must be a positive integer."))
    try:
        with connect(read_only=True) as connection:
            ticket, related = ticket_bundle(connection, ticket_id)
    except (FileNotFoundError, sqlite3.Error):
        return TicketResult(ok=False, error=err("database_unavailable", "The working operational database is unavailable."))
    if ticket is None:
        return TicketResult(ok=False, error=err("ticket_not_found", "No ticket has that id."))
    return TicketResult(ok=True, ticket=ticket, related=related)


@mcp.tool(name="check_inventory", description="Check exact inventory and pricing for a SKU, optionally restricted to one size.")
def check_inventory(sku: str, size: str | None = None) -> InventoryResult:
    normalized_sku = sku.strip().upper() if isinstance(sku, str) else ""
    if not valid_sku(normalized_sku):
        return InventoryResult(ok=False, sku=normalized_sku, error=err("invalid_sku", "sku must contain only uppercase letters, numbers, and hyphens."))
    normalized_size = size.strip().upper() if isinstance(size, str) and size.strip() else None
    if size is not None and normalized_size is None:
        return InventoryResult(ok=False, sku=normalized_sku, error=err("invalid_size", "size must be omitted or non-empty."))
    try:
        with connect(read_only=True) as connection:
            sql = "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?"
            args: tuple[str, ...] = (normalized_sku,)
            if normalized_size is not None:
                sql += " AND upper(size) = ?"
                args = (normalized_sku, normalized_size)
            sql += " ORDER BY size"
            inventory = rows_dict(connection.execute(sql, args).fetchall())
            pricing = row_dict(connection.execute("SELECT * FROM pricing WHERE sku = ?", (normalized_sku,)).fetchone())
    except (FileNotFoundError, sqlite3.Error):
        return InventoryResult(ok=False, sku=normalized_sku, error=err("database_unavailable", "The working operational database is unavailable."))
    if not pricing and not inventory:
        return InventoryResult(ok=False, sku=normalized_sku, size=normalized_size, error=err("sku_not_found", "No inventory or pricing record has that SKU."))
    if normalized_size is not None and not inventory:
        return InventoryResult(ok=False, sku=normalized_sku, size=normalized_size, pricing=pricing, error=err("size_not_found", "No inventory row exists for that SKU and size."))
    return InventoryResult(ok=True, sku=normalized_sku, size=normalized_size, inventory=inventory, pricing=pricing)


@mcp.tool(name="inspect_financial_obligation", description="Inspect the invoice or lease obligation attached to a ticket with cash and payment evidence.")
def inspect_financial_obligation(ticket_id: int) -> ObligationResult:
    if not valid_ticket_id(ticket_id):
        return ObligationResult(ok=False, ticket_id=0, error=err("invalid_ticket_id", "ticket_id must be a positive integer."))
    try:
        with connect(read_only=True) as connection:
            ticket = row_dict(connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
            if ticket is None:
                return ObligationResult(ok=False, ticket_id=ticket_id, error=err("ticket_not_found", "No ticket has that id."))
            obligation = None
            if ticket["invoice_id"]:
                obligation = row_dict(connection.execute("""
                    SELECT i.*, v.name AS vendor_name, v.specialty, v.lead_days
                    FROM invoices i JOIN vendors v ON v.id=i.vendor_id WHERE i.id=?
                """, (ticket["invoice_id"],)).fetchone())
            elif ticket["lease_id"]:
                obligation = row_dict(connection.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone())
            cash = rows_dict(connection.execute("SELECT * FROM cash_accounts ORDER BY name").fetchall())
            payments = rows_dict(connection.execute("SELECT * FROM payments WHERE ref_id = ? ORDER BY id", (ticket["invoice_id"] or ticket["lease_id"],)).fetchall())
            requests = rows_dict(connection.execute("SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall())
    except (FileNotFoundError, sqlite3.Error):
        return ObligationResult(ok=False, ticket_id=ticket_id, error=err("database_unavailable", "The working operational database is unavailable."))
    return ObligationResult(ok=True, ticket_id=ticket_id, obligation=obligation, cash_accounts=cash, existing_payments=payments, payment_requests=requests)


@mcp.tool(name="get_cash_balance", description="Read current cash account balances without changing them.")
def get_cash_balance(account: str = "checking") -> CashResult:
    normalized = account.strip().lower() if isinstance(account, str) else ""
    try:
        with connect(read_only=True) as connection:
            accounts = rows_dict(connection.execute("SELECT * FROM cash_accounts WHERE lower(name) = ?", (normalized,)).fetchall())
    except (FileNotFoundError, sqlite3.Error):
        return CashResult(ok=False, account=normalized, error=err("database_unavailable", "The working operational database is unavailable."))
    if not accounts:
        return CashResult(ok=False, account=normalized, error=err("account_not_found", "No cash account has that name."))
    return CashResult(ok=True, account=normalized, accounts=accounts)


@mcp.tool(name="prepare_payment_request", description="Prepare a pending payment request for a legitimate invoice or lease ticket; never executes payment or changes cash.")
def prepare_payment_request(ticket_id: int, requested_by: str, reason: str) -> PaymentRequestResult:
    if not valid_ticket_id(ticket_id):
        return PaymentRequestResult(ok=False, error=err("invalid_ticket_id", "ticket_id must be a positive integer."))
    requester = requested_by.strip() if isinstance(requested_by, str) else ""
    explanation = reason.strip() if isinstance(reason, str) else ""
    if not requester or len(requester) > 80:
        return PaymentRequestResult(ok=False, error=err("invalid_requester", "requested_by is required and must be at most 80 characters."))
    if not explanation or len(explanation) > 500:
        return PaymentRequestResult(ok=False, error=err("invalid_reason", "reason is required and must be at most 500 characters."))
    try:
        with connect() as connection:
            ticket = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if ticket is None:
                return PaymentRequestResult(ok=False, error=err("ticket_not_found", "No ticket has that id."))
            if ticket["status"] != "open":
                return PaymentRequestResult(ok=False, error=err("ticket_not_open", "Only open tickets can receive a new payment request."))
            if ticket["invoice_id"]:
                obligation = connection.execute("SELECT id, amount, status FROM invoices WHERE id = ?", (ticket["invoice_id"],)).fetchone()
                kind, ref_id = "invoice", ticket["invoice_id"]
            elif ticket["lease_id"]:
                obligation = connection.execute("SELECT id, monthly_rent AS amount, 'open' AS status FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone()
                kind, ref_id = "lease", ticket["lease_id"]
            else:
                return PaymentRequestResult(ok=False, error=err("no_payable_obligation", "This ticket has no invoice or lease obligation."))
            if obligation is None:
                return PaymentRequestResult(ok=False, error=err("obligation_not_found", "The ticket references a missing financial obligation."))
            if obligation["status"] not in ("open", "due"):
                return PaymentRequestResult(ok=False, error=err("obligation_not_open", "The obligation is not open for payment."))
            duplicate_payment = connection.execute(
                "SELECT 1 FROM payments WHERE kind = ? AND ref_id = ? AND account = ? LIMIT 1",
                (kind, ref_id, "checking"),
            ).fetchone()
            if duplicate_payment is not None:
                return PaymentRequestResult(ok=False, error=err("duplicate_payment", "A payment for this obligation already exists."))
            existing = connection.execute("""
                SELECT * FROM payment_requests
                WHERE ticket_id = ? AND kind = ? AND ref_id = ? AND status = 'pending'
                ORDER BY id DESC LIMIT 1
            """, (ticket_id, kind, ref_id)).fetchone()
            if existing is not None:
                return PaymentRequestResult(ok=True, request=dict(existing))
            cursor = connection.execute("""
                INSERT INTO payment_requests(ticket_id, kind, ref_id, amount, account, reason, status, requested_by)
                VALUES (?, ?, ?, ?, 'checking', ?, 'pending', ?)
            """, (ticket_id, kind, ref_id, float(obligation["amount"]), explanation, requester))
            request = connection.execute("SELECT * FROM payment_requests WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except (FileNotFoundError, sqlite3.Error):
        return PaymentRequestResult(ok=False, error=err("database_unavailable", "The working operational database is unavailable."))
    return PaymentRequestResult(ok=True, request=dict(request) if request else None)


if __name__ == "__main__":
    ensure_runtime_schema()
    mcp.run()

