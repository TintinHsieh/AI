"""Bounded SQLite tools exposed to the Campus Customs PydanticAI agent."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

try:
    from .models import ProductMatch, StockLevel
except ImportError:  # Supports running the backend package directly from backend/.
    from models import ProductMatch, StockLevel


MAX_TOOL_RESULTS = 8
SEARCH_CACHE_TTL_SECONDS = 30.0
SEARCH_CACHE_MAX_ENTRIES = 128
_SEARCH_CACHE: dict[tuple[str, str, int, bool], tuple[float, list[ProductMatch]]] = {}


@dataclass
class AgentDeps:
    """Per-request state shared by tools and the final response assembly."""

    db_path: Path
    user_id: int | None = None
    user_name: str | None = None
    user_email: str | None = None
    page_context: dict[str, object] = field(default_factory=dict)
    availability_requested: bool = False
    matches: dict[str, ProductMatch] = field(default_factory=dict)
    audit_run_id: str | None = None


def open_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _product_match(
    row: sqlite3.Row,
    inventory_rows: list[sqlite3.Row],
) -> ProductMatch:
    stock = [StockLevel(size=item["size"], quantity=item["quantity"]) for item in inventory_rows]
    image_path = row["image_file_path"]
    return ProductMatch(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        price=float(row["price"]),
        image_url=f"/api/images/{quote(image_path, safe='/')}",
        colors=parse_json_list(row["colors"]),
        stock=stock,
        total_stock=sum(level.quantity for level in stock),
    )


def _remember(deps: AgentDeps, matches: list[ProductMatch]) -> list[ProductMatch]:
    for match in matches:
        deps.matches[match.product_id] = match
    return matches[:MAX_TOOL_RESULTS]


def _store_search_cache(
    key: tuple[str, str, int, bool],
    matches: list[ProductMatch],
) -> None:
    if key not in _SEARCH_CACHE and len(_SEARCH_CACHE) >= SEARCH_CACHE_MAX_ENTRIES:
        _SEARCH_CACHE.pop(next(iter(_SEARCH_CACHE)))
    _SEARCH_CACHE[key] = (time.monotonic(), [match.model_copy(deep=True) for match in matches])


def search_catalogue(
    deps: AgentDeps,
    query: str,
    limit: int = 6,
    in_stock_only: bool = False,
) -> list[ProductMatch]:
    """Search factual product fields, optionally requiring positive inventory."""

    clean_query = query.strip().lower()
    if not clean_query:
        return []
    bounded_limit = max(1, min(int(limit), MAX_TOOL_RESULTS))
    if deps.availability_requested or any(phrase in clean_query for phrase in ("in stock", "available", "on hand")):
        in_stock_only = True
    cache_key = (str(deps.db_path.resolve()), clean_query, bounded_limit, in_stock_only)
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < SEARCH_CACHE_TTL_SECONDS:
        return _remember(deps, [match.model_copy(deep=True) for match in cached[1]])
    stop_words = {"a", "about", "and", "do", "for", "have", "i", "me", "of", "please", "show", "the", "what", "you"}
    tokens = [token for token in re.findall(r"[a-z0-9-]+", clean_query) if token not in stop_words]
    terms = [clean_query, *tokens]
    for token in tokens:
        if token.endswith("ies") and len(token) > 3:
            terms.extend([token[:-1], f"{token[:-3]}y"])
        elif token.endswith("s") and len(token) > 3:
            terms.append(token[:-1])
    unique_terms = list(dict.fromkeys(term for term in terms if term))
    conditions: list[str] = []
    params: list[str] = []
    for value in unique_terms:
        term = f"%{value}%"
        conditions.append(
            "(lower(name) LIKE ? OR lower(garment_type) LIKE ? OR lower(description) LIKE ? "
            "OR lower(colors) LIKE ? OR lower(search_tags) LIKE ?)"
        )
        params.extend([term] * 5)
    first_term = f"%{unique_terms[0]}%"
    connection = open_db(deps.db_path)
    try:
        stock_clause = "AND EXISTS (SELECT 1 FROM inventory WHERE inventory.product_id = catalogue.product_id AND quantity > 0)" if in_stock_only else ""
        rows = connection.execute(
            f"""
            SELECT * FROM catalogue
            WHERE {' OR '.join(conditions)}
              {stock_clause}
            ORDER BY
                CASE WHEN lower(name) LIKE ? THEN 0
                     WHEN lower(garment_type) LIKE ? THEN 1
                     ELSE 2 END,
                name COLLATE NOCASE
            LIMIT ?
            """,
            (*params, first_term, first_term, bounded_limit),
        ).fetchall()
        if not rows:
            _store_search_cache(cache_key, [])
            return []
        ids = [row["product_id"] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        inventory_rows = connection.execute(
            f"SELECT product_id, size, quantity FROM inventory WHERE product_id IN ({placeholders}) ORDER BY product_id, size",
            ids,
        ).fetchall()
        inventory_by_product: dict[str, list[sqlite3.Row]] = {}
        for inventory_row in inventory_rows:
            inventory_by_product.setdefault(inventory_row["product_id"], []).append(inventory_row)
        matches = [_product_match(row, inventory_by_product.get(row["product_id"], [])) for row in rows]
        _store_search_cache(cache_key, matches)
        return _remember(deps, matches)
    finally:
        connection.close()


def get_product_inventory(deps: AgentDeps, product_id: str) -> ProductMatch | None:
    """Look up one exact product and its per-size stock from SQLite."""

    clean_id = product_id.strip()
    connection = open_db(deps.db_path)
    try:
        row = connection.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (clean_id,)
        ).fetchone()
        if row is None:
            return None
        inventory_rows = connection.execute(
            "SELECT product_id, size, quantity FROM inventory WHERE product_id = ? ORDER BY size",
            (clean_id,),
        ).fetchall()
        return _remember(deps, [_product_match(row, inventory_rows)])[0]
    finally:
        connection.close()
