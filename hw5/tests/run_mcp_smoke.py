"""Run Problem 4 MCP integration checks from the project .mcp.json file.

The MCP calls use FastMCP Client with the exact project configuration. The
independent checks use a separate read-only sqlite3 connection and do not
import mcp_server.py or reuse its SQL helpers.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import Client


PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_DIR / ".mcp.json"
DATABASE_PATH = PROJECT_DIR / "data" / "campus_customs_working.db"
EXPECTED_TOOLS = {
    "search_catalogue",
    "check_inventory",
    "get_customer_chat_history",
}


def read_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    server = config["mcpServers"]["campus-customs"]
    assert server["cwd"] == str(PROJECT_DIR)
    assert server["args"] == ["mcp_server.py"]
    assert Path(server["command"]).is_file()
    return config


def open_database() -> sqlite3.Connection:
    connection = sqlite3.connect(f"{DATABASE_PATH.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def independent_search(query: str, limit: int, in_stock_only: bool) -> list[dict[str, Any]]:
    pattern = f"%{query.lower()}%"
    with open_database() as connection:
        rows = connection.execute(
            """
            SELECT c.product_id, c.name, c.price, COALESCE(SUM(i.quantity), 0) AS total_stock
            FROM catalogue AS c
            LEFT JOIN inventory AS i ON i.product_id = c.product_id
            WHERE lower(c.product_id) LIKE ?
               OR lower(c.name) LIKE ?
               OR lower(c.garment_type) LIKE ?
               OR lower(c.description) LIKE ?
               OR lower(c.colors) LIKE ?
               OR lower(c.search_tags) LIKE ?
            GROUP BY c.product_id
            HAVING (? = 0 OR total_stock > 0)
            ORDER BY c.name COLLATE NOCASE
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern, int(in_stock_only), limit),
        ).fetchall()
    return [
        {
            "product_id": row["product_id"],
            "name": row["name"],
            "price": float(row["price"]),
            "total_stock": int(row["total_stock"]),
        }
        for row in rows
    ]


def independent_inventory(product_id: str) -> dict[str, Any] | None:
    with open_database() as connection:
        product = connection.execute(
            "SELECT product_id, name, price FROM catalogue WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if product is None:
            return None
        rows = connection.execute(
            """
            SELECT size, quantity
            FROM inventory
            WHERE product_id = ?
            ORDER BY CASE size WHEN 'XS' THEN 1 WHEN 'S' THEN 2 WHEN 'M' THEN 3
                              WHEN 'L' THEN 4 WHEN 'XL' THEN 5 WHEN 'XXL' THEN 6 ELSE 7 END,
                     size
            """,
            (product_id,),
        ).fetchall()
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "price": float(product["price"]),
        "total_stock": sum(int(row["quantity"]) for row in rows),
        "inventory": [{"size": row["size"], "quantity": int(row["quantity"])} for row in rows],
    }


def independent_history(user_id: int, limit: int) -> list[dict[str, Any]]:
    with open_database() as connection:
        rows = connection.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [
        {
            "message_id": int(row["id"]),
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in reversed(rows)
    ]


def record(
    tool_name: str,
    arguments: dict[str, Any],
    returned_result: dict[str, Any],
    independent_check: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "returned_result": returned_result,
        "independent_check": independent_check,
        "matches_independent_check": bool(independent_check.get("matches")),
    }


async def run_smoke() -> dict[str, Any]:
    config = read_config()
    checks: list[dict[str, Any]] = []

    async with Client(config) as client:
        advertised = sorted(tool.name for tool in await client.list_tools())
        checks.append(
            {
                "test": "tool_discovery",
                "tool_name": None,
                "arguments": {},
                "returned_result": {"tool_names": advertised},
                "independent_check": {
                    "method": "expected_protocol_tool_set",
                    "expected_tool_names": sorted(EXPECTED_TOOLS),
                    "matches": set(advertised) == EXPECTED_TOOLS,
                },
                "matches_independent_check": set(advertised) == EXPECTED_TOOLS,
            }
        )
        assert set(advertised) == EXPECTED_TOOLS

        search_args = {"query": "hoodie", "limit": 4, "in_stock_only": True}
        search = await client.call_tool("search_catalogue", search_args)
        search_result = search.structured_content
        expected_search = independent_search("hoodie", 4, True)
        actual_search = [
            {
                "product_id": item["product_id"],
                "name": item["name"],
                "price": item["price"],
                "total_stock": item["total_stock"],
            }
            for item in search_result["products"]
        ]
        checks.append(
            record(
                "search_catalogue",
                search_args,
                search_result,
                {
                    "method": "independent_read_only_sqlite_query",
                    "expected_products": expected_search,
                    "matches": search_result["ok"] is True and actual_search == expected_search,
                },
            )
        )

        inventory_args = {"product_id": "basic-hoodie-big-yale"}
        inventory = await client.call_tool("check_inventory", inventory_args)
        inventory_result = inventory.structured_content
        expected_inventory = independent_inventory(inventory_args["product_id"])
        actual_inventory = {
            "product_id": inventory_result["product_id"],
            "name": inventory_result["name"],
            "price": inventory_result["price"],
            "total_stock": inventory_result["total_stock"],
            "inventory": inventory_result["inventory"],
        }
        checks.append(
            record(
                "check_inventory",
                inventory_args,
                inventory_result,
                {
                    "method": "independent_read_only_sqlite_query",
                    "expected_product": expected_inventory,
                    "matches": inventory_result["ok"] is True and actual_inventory == expected_inventory,
                },
            )
        )

        history_args = {"user_id": 1, "limit": 2}
        history = await client.call_tool("get_customer_chat_history", history_args)
        history_result = history.structured_content
        expected_history = independent_history(1, 2)
        actual_history = [
            {
                "message_id": message["message_id"],
                "role": message["role"],
                "content": message["content"],
                "created_at": message["created_at"],
            }
            for message in history_result["messages"]
        ]
        checks.append(
            record(
                "get_customer_chat_history",
                history_args,
                history_result,
                {
                    "method": "independent_read_only_sqlite_query",
                    "expected_messages": expected_history,
                    "matches": history_result["ok"] is True and actual_history == expected_history,
                },
            )
        )

        missing_product_args = {"product_id": "not-a-real-product"}
        missing_product = await client.call_tool("check_inventory", missing_product_args)
        missing_product_result = missing_product.structured_content
        expected_missing = independent_inventory(missing_product_args["product_id"])
        checks.append(
            record(
                "check_inventory",
                missing_product_args,
                missing_product_result,
                {
                    "method": "independent_read_only_sqlite_query",
                    "expected_product": expected_missing,
                    "matches": expected_missing is None
                    and missing_product_result["ok"] is False
                    and missing_product_result["error"]["code"] == "product_not_found",
                },
            )
        )

        invalid_search_args = {"query": " "}
        invalid_search = await client.call_tool("search_catalogue", invalid_search_args)
        invalid_search_result = invalid_search.structured_content
        checks.append(
            record(
                "search_catalogue",
                invalid_search_args,
                invalid_search_result,
                {
                    "method": "independent_input_validation_check",
                    "expected_error": "invalid_query",
                    "matches": invalid_search_result["ok"] is False
                    and invalid_search_result["error"]["code"] == "invalid_query",
                },
            )
        )

    all_matches = all(item["matches_independent_check"] for item in checks)
    return {
        "schema_version": "hw5.problem4.mcp_smoke.v1",
        "status": "passed" if all_matches else "failed",
        "config_path": str(CONFIG_PATH),
        "server_config": config["mcpServers"]["campus-customs"],
        "database_path": str(DATABASE_PATH),
        "ticket_source": {
            "available": False,
            "note": (
                "No ticket records or assignment ticket payloads were present in the supplied workspace. "
                "Inputs are representative real database workflows and are not labeled as ticket-derived."
            ),
        },
        "checks": checks,
        "all_results_match_independent_checks": all_matches,
    }


if __name__ == "__main__":
    output_path = PROJECT_DIR / "output" / "mcp_smoke.json"
    evidence = asyncio.run(run_smoke())
    output_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if evidence["status"] != "passed":
        raise SystemExit(1)

