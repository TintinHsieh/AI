"""Protocol smoke evidence for the authoritative HW5 operational database."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import Client


PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_DIR / ".mcp.json"
DB_PATH = PROJECT_DIR / "data" / "campus_customs_working.db"
EXPECTED_TOOLS = {
    "inspect_ticket",
    "check_inventory",
    "inspect_financial_obligation",
    "get_cash_balance",
    "prepare_payment_request",
}


def config() -> dict[str, Any]:
    value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    server = value["mcpServers"]["campus-customs"]
    assert server["args"] == ["mcp_operational_server.py"]
    assert server["cwd"] == str(PROJECT_DIR)
    assert Path(server["command"]).is_file()
    return value


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def row(value: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(value) if value is not None else None


def all_rows(values: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(value) for value in values]


def check(name: str, args: dict[str, Any], returned: dict[str, Any], expected: Any, matches: bool, method: str) -> dict[str, Any]:
    return {
        "tool_name": name,
        "arguments": args,
        "returned_result": returned,
        "independent_check": {"method": method, "expected": expected, "matches": matches},
        "matches_independent_check": matches,
    }


async def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    async with Client(config()) as client:
        advertised = sorted(tool.name for tool in await client.list_tools())
        checks.append(check("<discovery>", {}, {"tool_names": advertised}, sorted(EXPECTED_TOOLS), set(advertised) == EXPECTED_TOOLS, "expected_expanded_tool_set"))

        for ticket_id in (101, 102, 103):
            args = {"ticket_id": ticket_id}
            result = (await client.call_tool("inspect_ticket", args)).structured_content
            with db() as connection:
                expected = row(connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
            checks.append(check("inspect_ticket", args, result, {"ticket_id": ticket_id, "status": expected["status"] if expected else None}, result["ok"] and result["ticket"]["id"] == ticket_id and result["ticket"]["status"] == expected["status"], "ticket_row_and_status_query"))

        inventory_args = {"sku": "CC-TEE-WHITE", "size": "S"}
        inventory = (await client.call_tool("check_inventory", inventory_args)).structured_content
        with db() as connection:
            expected_inventory = row(connection.execute("SELECT * FROM inventory WHERE sku = ? AND size = ?", ("CC-TEE-WHITE", "S")).fetchone())
            expected_price = row(connection.execute("SELECT * FROM pricing WHERE sku = ?", ("CC-TEE-WHITE",)).fetchone())
        checks.append(check("check_inventory", inventory_args, inventory, {"inventory": expected_inventory, "pricing": expected_price}, inventory["ok"] and inventory["inventory"] == [expected_inventory] and inventory["pricing"] == expected_price, "inventory_and_pricing_query"))

        for ticket_id in (101, 102):
            args = {"ticket_id": ticket_id}
            result = (await client.call_tool("inspect_financial_obligation", args)).structured_content
            with db() as connection:
                ticket = row(connection.execute("SELECT invoice_id, lease_id FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
                cash = all_rows(connection.execute("SELECT * FROM cash_accounts").fetchall())
            checks.append(check("inspect_financial_obligation", args, result, {"cash_accounts": cash, "obligation_type": "invoice" if ticket["invoice_id"] else "lease"}, result["ok"] and result["cash_accounts"] == cash and result["obligation"] is not None, "obligation_and_cash_query"))

        cash_args = {"account": "checking"}
        cash_result = (await client.call_tool("get_cash_balance", cash_args)).structured_content
        with db() as connection:
            expected_cash = all_rows(connection.execute("SELECT * FROM cash_accounts WHERE name = 'checking'").fetchall())
        checks.append(check("get_cash_balance", cash_args, cash_result, expected_cash, cash_result["ok"] and cash_result["accounts"] == expected_cash, "cash_account_query"))

        prep_args = {"ticket_id": 101, "requested_by": "Boss", "reason": "Prepare invoice review for human approval; do not execute."}
        prep_result = (await client.call_tool("prepare_payment_request", prep_args)).structured_content
        with db() as connection:
            expected_request = row(connection.execute("SELECT * FROM payment_requests WHERE ticket_id = 101 AND status = 'pending' ORDER BY id DESC LIMIT 1").fetchone())
            payment_count = connection.execute("SELECT count(*) FROM payments").fetchone()[0]
        checks.append(check("prepare_payment_request", prep_args, prep_result, {"status": expected_request["status"] if expected_request else None, "payment_count": payment_count}, prep_result["ok"] and prep_result["request"]["status"] == "pending" and payment_count == 0, "payment_request_and_no_payment_query"))

        invalid_args = {"ticket_id": 999}
        invalid = (await client.call_tool("inspect_ticket", invalid_args)).structured_content
        checks.append(check("inspect_ticket", invalid_args, invalid, {"error": "ticket_not_found"}, not invalid["ok"] and invalid["error"]["code"] == "ticket_not_found", "missing_ticket_query"))

    passed = all(item["matches_independent_check"] for item in checks)
    return {
        "schema_version": "hw5.problem5.operational_mcp_smoke.v1",
        "status": "passed" if passed else "failed",
        "config_path": str(CONFIG_PATH),
        "database_path": str(DB_PATH),
        "tickets_tested": [101, 102, 103],
        "checks": checks,
        "all_results_match_independent_checks": passed,
        "note": "Payment preparation was tested as pending only; no payment was executed by MCP.",
    }


if __name__ == "__main__":
    evidence = asyncio.run(run())
    output = PROJECT_DIR / "output" / "mcp_smoke.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if evidence["status"] != "passed":
        raise SystemExit(1)

