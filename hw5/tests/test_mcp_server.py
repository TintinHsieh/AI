"""Protocol smoke test for the Problem 3 Campus Customs MCP server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastmcp import Client


SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp_server.py"
EXPECTED_TOOLS = {
    "search_catalogue",
    "check_inventory",
    "get_customer_chat_history",
}


async def run_checks() -> dict[str, object]:
    """Launch the server over stdio and exercise success/error paths."""

    async with Client(str(SERVER_PATH)) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert tool_names == EXPECTED_TOOLS, tool_names

        search = await client.call_tool(
            "search_catalogue",
            {"query": "hoodie", "limit": 4, "in_stock_only": True},
        )
        search_data = search.structured_content
        assert search_data["ok"] is True
        assert 0 < len(search_data["products"]) <= 4
        assert all(item["total_stock"] > 0 for item in search_data["products"])

        inventory = await client.call_tool(
            "check_inventory",
            {"product_id": "basic-hoodie-big-yale"},
        )
        inventory_data = inventory.structured_content
        assert inventory_data["ok"] is True
        assert inventory_data["total_stock"] == 60
        assert len(inventory_data["inventory"]) == 6

        history = await client.call_tool(
            "get_customer_chat_history",
            {"user_id": 1, "limit": 2},
        )
        history_data = history.structured_content
        assert history_data["ok"] is True
        assert len(history_data["messages"]) == 2

        missing = await client.call_tool(
            "check_inventory",
            {"product_id": "not-a-real-product"},
        )
        missing_data = missing.structured_content
        assert missing_data["ok"] is False
        assert missing_data["error"]["code"] == "product_not_found"

        invalid_search = await client.call_tool("search_catalogue", {"query": " "})
        invalid_search_data = invalid_search.structured_content
        assert invalid_search_data["ok"] is False
        assert invalid_search_data["error"]["code"] == "invalid_query"

        invalid_id = await client.call_tool(
            "check_inventory",
            {"product_id": "' OR 1=1 --"},
        )
        invalid_id_data = invalid_id.structured_content
        assert invalid_id_data["ok"] is False
        assert invalid_id_data["error"]["code"] == "invalid_product_id"

        missing_user = await client.call_tool(
            "get_customer_chat_history",
            {"user_id": 999999},
        )
        missing_user_data = missing_user.structured_content
        assert missing_user_data["ok"] is False
        assert missing_user_data["error"]["code"] == "user_not_found"

        return {
            "advertised_tools": sorted(tool_names),
            "hoodie_results": len(search_data["products"]),
            "basic_hoodie_total_stock": inventory_data["total_stock"],
            "history_messages_checked": len(history_data["messages"]),
            "missing_product_error": missing_data["error"]["code"],
            "invalid_query_error": invalid_search_data["error"]["code"],
            "invalid_product_id_error": invalid_id_data["error"]["code"],
            "missing_user_error": missing_user_data["error"]["code"],
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_checks()), indent=2))

