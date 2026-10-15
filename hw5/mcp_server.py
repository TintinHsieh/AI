"""Read-only MCP tools for the Campus Customs working database.

The server intentionally binds to the Problem 2 working copy. It never accepts
an arbitrary database path and exposes business operations rather than SQL.
The default transport is stdio so an MCP host can launch this file directly.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field


PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = (PROJECT_DIR / "data" / "campus_customs_working.db").resolve()
MAX_SEARCH_RESULTS = 20
MAX_HISTORY_MESSAGES = 100
PRODUCT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

mcp = FastMCP(
    name="Campus Customs Operations",
    instructions=(
        "Use the three read-only business tools to inspect catalogue facts, "
        "size-level inventory, and persisted customer chat context. "
        "The database does not contain ticket, order, purchasing, payment, "
        "bank, or facilities records."
    ),
)


class ToolError(BaseModel):
    """Stable, non-sensitive error information returned by every tool."""

    code: str
    message: str


class ProductHit(BaseModel):
    """A bounded catalogue result with aggregate stock."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str] = Field(default_factory=list)
    total_stock: int


class SearchCatalogueResult(BaseModel):
    ok: bool
    query: str
    in_stock_only: bool
    products: list[ProductHit] = Field(default_factory=list)
    error: ToolError | None = None


class InventoryRow(BaseModel):
    size: str
    quantity: int


class InventoryResult(BaseModel):
    ok: bool
    product_id: str
    name: str | None = None
    garment_type: str | None = None
    price: float | None = None
    colors: list[str] = Field(default_factory=list)
    total_stock: int | None = None
    inventory: list[InventoryRow] = Field(default_factory=list)
    error: ToolError | None = None


class ChatMessageRecord(BaseModel):
    message_id: int
    role: str
    content: str
    created_at: str
    product_ids: list[str] = Field(default_factory=list)
    product_count: int = 0
    product_payload_valid: bool = True


class ChatHistoryResult(BaseModel):
    ok: bool
    user_id: int
    messages: list[ChatMessageRecord] = Field(default_factory=list)
    error: ToolError | None = None


def _error(code: str, message: str) -> ToolError:
    return ToolError(code=code, message=message)


def _empty_db_error() -> ToolError:
    return _error(
        "database_unavailable",
        "The Campus Customs working database is not available.",
    )


def _open_read_only() -> sqlite3.Connection:
    """Open only the fixed working copy and force a no-write connection."""

    if not DB_PATH.is_file():
        raise FileNotFoundError(str(DB_PATH))

    connection = sqlite3.connect(
        f"{DB_PATH.as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _parse_json_list(value: str | None) -> tuple[list[str], bool]:
    """Parse a JSON string array without allowing malformed data to break a tool."""

    if value is None:
        return [], True
    try:
        parsed: Any = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [], False
    if not isinstance(parsed, list):
        return [], False
    return [str(item) for item in parsed], True


def _parse_product_ids(value: str | None) -> tuple[list[str], int, bool]:
    """Extract only product ids from persisted structured chat results."""

    if value is None:
        return [], 0, True
    try:
        parsed: Any = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [], 0, False
    if not isinstance(parsed, list):
        return [], 0, False

    product_ids: list[str] = []
    for item in parsed:
        if isinstance(item, dict) and isinstance(item.get("product_id"), str):
            product_ids.append(item["product_id"])
    return product_ids, len(parsed), True


def _valid_limit(value: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= maximum


@mcp.tool(
    name="search_catalogue",
    description=(
        "Search Campus Customs catalogue facts by product text, garment type, "
        "description, colors, or search tags. Returns bounded products with "
        "price and aggregate inventory; it never executes caller-supplied SQL."
    ),
)
def search_catalogue(
    query: str,
    limit: int = 8,
    in_stock_only: bool = False,
) -> SearchCatalogueResult:
    """Answer a bounded product-search question from catalogue and inventory."""

    normalized_query = query.strip() if isinstance(query, str) else ""
    if not normalized_query:
        return SearchCatalogueResult(
            ok=False,
            query="",
            in_stock_only=in_stock_only,
            error=_error("invalid_query", "query must contain at least one character."),
        )
    if len(normalized_query) > 120:
        return SearchCatalogueResult(
            ok=False,
            query=normalized_query[:120],
            in_stock_only=in_stock_only,
            error=_error("invalid_query", "query must be at most 120 characters."),
        )
    if not _valid_limit(limit, MAX_SEARCH_RESULTS):
        return SearchCatalogueResult(
            ok=False,
            query=normalized_query,
            in_stock_only=in_stock_only,
            error=_error("invalid_limit", f"limit must be between 1 and {MAX_SEARCH_RESULTS}."),
        )
    if not isinstance(in_stock_only, bool):
        return SearchCatalogueResult(
            ok=False,
            query=normalized_query,
            in_stock_only=False,
            error=_error("invalid_stock_filter", "in_stock_only must be a boolean."),
        )

    pattern = f"%{normalized_query.lower()}%"
    sql = """
        SELECT
            c.product_id,
            c.name,
            c.garment_type,
            c.price,
            c.colors,
            COALESCE(SUM(i.quantity), 0) AS total_stock
        FROM catalogue AS c
        LEFT JOIN inventory AS i ON i.product_id = c.product_id
        WHERE (
            lower(c.product_id) LIKE ?
            OR lower(c.name) LIKE ?
            OR lower(c.garment_type) LIKE ?
            OR lower(c.description) LIKE ?
            OR lower(c.colors) LIKE ?
            OR lower(c.search_tags) LIKE ?
        )
        GROUP BY c.product_id
        HAVING (? = 0 OR total_stock > 0)
        ORDER BY c.name COLLATE NOCASE
        LIMIT ?
    """

    try:
        with _open_read_only() as connection:
            rows = connection.execute(
                sql,
                (pattern, pattern, pattern, pattern, pattern, pattern, int(in_stock_only), limit),
            ).fetchall()
    except (FileNotFoundError, sqlite3.Error):
        return SearchCatalogueResult(
            ok=False,
            query=normalized_query,
            in_stock_only=in_stock_only,
            error=_empty_db_error(),
        )

    products: list[ProductHit] = []
    for row in rows:
        colors, valid_colors = _parse_json_list(row["colors"])
        if not valid_colors:
            colors = []
        products.append(
            ProductHit(
                product_id=row["product_id"],
                name=row["name"],
                garment_type=row["garment_type"],
                price=float(row["price"]),
                colors=colors,
                total_stock=int(row["total_stock"]),
            )
        )
    return SearchCatalogueResult(
        ok=True,
        query=normalized_query,
        in_stock_only=in_stock_only,
        products=products,
    )


@mcp.tool(
    name="check_inventory",
    description=(
        "Look up one known Campus Customs product and its size-level stock. "
        "Pass size to check one variant or omit it for all sizes."
    ),
)
def check_inventory(product_id: str, size: str | None = None) -> InventoryResult:
    """Return authoritative inventory for one catalogue product."""

    normalized_product_id = product_id.strip() if isinstance(product_id, str) else ""
    if not PRODUCT_ID_PATTERN.fullmatch(normalized_product_id):
        return InventoryResult(
            ok=False,
            product_id=normalized_product_id,
            error=_error("invalid_product_id", "product_id has an invalid format."),
        )

    normalized_size: str | None
    if size is None:
        normalized_size = None
    elif isinstance(size, str) and size.strip():
        normalized_size = size.strip().upper()
        if len(normalized_size) > 16:
            return InventoryResult(
                ok=False,
                product_id=normalized_product_id,
                error=_error("invalid_size", "size must be at most 16 characters."),
            )
    else:
        return InventoryResult(
            ok=False,
            product_id=normalized_product_id,
            error=_error("invalid_size", "size must be omitted or a non-empty string."),
        )

    try:
        with _open_read_only() as connection:
            product = connection.execute(
                """
                SELECT product_id, name, garment_type, price, colors
                FROM catalogue
                WHERE product_id = ?
                """,
                (normalized_product_id,),
            ).fetchone()
            if product is None:
                return InventoryResult(
                    ok=False,
                    product_id=normalized_product_id,
                    error=_error("product_not_found", "No catalogue product has that product_id."),
                )

            stock_sql = """
                SELECT size, quantity
                FROM inventory
                WHERE product_id = ?
            """
            parameters: tuple[str, ...] = (normalized_product_id,)
            if normalized_size is not None:
                stock_sql += " AND upper(size) = ?"
                parameters = (normalized_product_id, normalized_size)
            stock_sql += " ORDER BY CASE size WHEN 'XS' THEN 1 WHEN 'S' THEN 2 WHEN 'M' THEN 3 WHEN 'L' THEN 4 WHEN 'XL' THEN 5 WHEN 'XXL' THEN 6 ELSE 7 END, size"
            rows = connection.execute(stock_sql, parameters).fetchall()
            all_stock = connection.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM inventory WHERE product_id = ?",
                (normalized_product_id,),
            ).fetchone()[0]
    except (FileNotFoundError, sqlite3.Error):
        return InventoryResult(
            ok=False,
            product_id=normalized_product_id,
            error=_empty_db_error(),
        )

    if normalized_size is not None and not rows:
        return InventoryResult(
            ok=False,
            product_id=normalized_product_id,
            name=product["name"],
            garment_type=product["garment_type"],
            price=float(product["price"]),
            error=_error("size_not_found", "That size has no inventory row for this product."),
        )

    colors, valid_colors = _parse_json_list(product["colors"])
    return InventoryResult(
        ok=True,
        product_id=normalized_product_id,
        name=product["name"],
        garment_type=product["garment_type"],
        price=float(product["price"]),
        colors=colors if valid_colors else [],
        total_stock=int(all_stock),
        inventory=[InventoryRow(size=row["size"], quantity=int(row["quantity"])) for row in rows],
    )


@mcp.tool(
    name="get_customer_chat_history",
    description=(
        "Read a bounded persisted conversation for a known user_id. Returns "
        "message text and safe product identifiers only; it never returns email "
        "addresses, password hashes, or arbitrary user-table fields."
    ),
)
def get_customer_chat_history(user_id: int, limit: int = 20) -> ChatHistoryResult:
    """Provide prior conversation context for a customer-service agent."""

    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        return ChatHistoryResult(
            ok=False,
            user_id=0 if not isinstance(user_id, int) else user_id,
            error=_error("invalid_user_id", "user_id must be a positive integer."),
        )
    if not _valid_limit(limit, MAX_HISTORY_MESSAGES):
        return ChatHistoryResult(
            ok=False,
            user_id=user_id,
            error=_error("invalid_limit", f"limit must be between 1 and {MAX_HISTORY_MESSAGES}."),
        )

    try:
        with _open_read_only() as connection:
            user_exists = connection.execute(
                "SELECT 1 FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user_exists is None:
                return ChatHistoryResult(
                    ok=False,
                    user_id=user_id,
                    error=_error("user_not_found", "No customer account has that user_id."),
                )
            rows = connection.execute(
                """
                SELECT id, role, content, products_json, created_at
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
    except (FileNotFoundError, sqlite3.Error):
        return ChatHistoryResult(
            ok=False,
            user_id=user_id,
            error=_empty_db_error(),
        )

    messages: list[ChatMessageRecord] = []
    for row in reversed(rows):
        product_ids, product_count, valid_payload = _parse_product_ids(row["products_json"])
        messages.append(
            ChatMessageRecord(
                message_id=int(row["id"]),
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
                product_ids=product_ids,
                product_count=product_count,
                product_payload_valid=valid_payload,
            )
        )
    return ChatHistoryResult(ok=True, user_id=user_id, messages=messages)


if __name__ == "__main__":
    mcp.run()

