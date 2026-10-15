# HW5 Problem 2 — Campus Customs database reference

## Scope and data safety

This reference describes the database that is actually present in the workspace. The HW5 assignment page, starter bundle, and the payloads for the three operational tickets were not present, so no ticket facts or business decisions are invented here.

- Original course data: `../HW4/data/campus_customs.db`
- Problem 2 working copy: `../data/campus_customs_working.db`
- Product images used by the catalogue: `../HW4/data/products/`

The working copy was created before inspection. The original and copy were both 180,224 bytes with SHA-256 `de3ac0cbcad229258c3fbd4b700f71e759e0965cd9f9054ec81cc79130c4aa6a`. The original modification timestamp remained `2026-10-07T02:30:38.239Z` after the copy and read-only queries. No insert, update, delete, schema change, or ticket-resolution operation was performed.

## Database inventory

The SQLite application tables are:

| Table | Rows | Purpose | Agent relevance |
| --- | ---: | --- | --- |
| `catalogue` | 102 | Product master data | Grounding for product identity, description, colors, tags, image paths, and prices. |
| `inventory` | 612 | One stock row per product and size | Source of truth for size-level availability and total stock. |
| `users` | 4 | Shopper accounts | Identifies account owners for authentication and persisted chat history. `password_hash` is sensitive and must never be exposed to an agent or MCP client. |
| `chat_messages` | 24 | Persisted user/assistant conversations | Provides prior conversational context and optional structured product matches. |

`sqlite_sequence` is SQLite’s internal AUTOINCREMENT bookkeeping table, not a business entity.

## Complete schema and constraints

### `catalogue`

Primary key: `product_id`. No foreign keys. SQLite created the primary-key auto-index `sqlite_autoindex_catalogue_1`.

| Column | Type | Required / constraint | Why it matters |
| --- | --- | --- | --- |
| `product_id` | `TEXT` | Primary key | Stable join key for inventory and agent/product results. |
| `name` | `TEXT` | `NOT NULL` | Customer-facing product name. |
| `garment_type` | `TEXT` | `NOT NULL` | Category used for catalogue retrieval. |
| `description` | `TEXT` | `NOT NULL` | Grounded product facts for shopper answers. |
| `colors` | `TEXT` | `NOT NULL`; JSON text array | Available product colors; parse before filtering. |
| `search_tags` | `TEXT` | `NOT NULL`; JSON text array | Search concepts such as school, sport, brand, and garment terms. |
| `image_file_path` | `TEXT` | `NOT NULL` | Relative path to the supplied product image. |
| `price` | `REAL` | `NOT NULL` | Current catalogue price. |

Representative query: `2025-yale-vs-harvard-t-shirt` is a short-sleeve T-shirt priced at `$32.00`; its colors and search tags are stored as JSON text, not child rows.

### `inventory`

Primary key: `id`. Foreign key: `product_id` → `catalogue.product_id`. Constraint: `UNIQUE (product_id, size)`, represented by `sqlite_autoindex_inventory_1`.

| Column | Type | Required / constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key, autoincrement | Stable inventory-row identifier. |
| `product_id` | `TEXT` | `NOT NULL`; foreign key to `catalogue` | Connects size stock to product facts and price. |
| `size` | `TEXT` | `NOT NULL` | Purchasable size variant. |
| `quantity` | `INTEGER` | `NOT NULL` | Authoritative stock count for the size. |

The first product’s queried rows include XS 25, S 25, M 20, L 2, and XL 25. Across the table, all 102 products have six size rows, totaling 5,920 units; 467 size rows have positive quantity and no product has a zero total across all sizes.

### `users`

Primary key: `id`. Unique constraint: `email`, represented by `sqlite_autoindex_users_1`. No foreign keys.

| Column | Type | Required / constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key, autoincrement | Account identity and parent key for chat history. |
| `name` | `TEXT` | `NOT NULL` | Combined display name. |
| `email` | `TEXT` | `NOT NULL`, unique | Login identifier. |
| `password_hash` | `TEXT` | `NOT NULL` | Authentication verifier; sensitive and excluded from agent/MCP output. |
| `created_at` | `TEXT` | `NOT NULL`, default `datetime('now')` | Account creation timestamp. |
| `first_name` | `TEXT` | Nullable | Registration/profile first name. |
| `last_name` | `TEXT` | Nullable | Registration/profile last name. |

The database has four accounts, and all four have first name, last name, and password-hash values. Account values and hashes are not reproduced here.

### `chat_messages`

Primary key: `id`. Foreign key: `user_id` → `users.id`. No secondary index was present.

| Column | Type | Required / constraint | Why it matters |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Primary key, autoincrement | Message identity and chronological ordering. |
| `user_id` | `INTEGER` | `NOT NULL`; foreign key to `users` | Associates history with an account. |
| `role` | `TEXT` | `NOT NULL` | Distinguishes `user` and `assistant` messages. No CHECK constraint restricts the values. |
| `content` | `TEXT` | `NOT NULL` | Visible message text. |
| `products_json` | `TEXT` | Nullable; JSON text when present | Structured product matches restored with assistant messages. |
| `created_at` | `TEXT` | `NOT NULL`, default `datetime('now')` | Conversation ordering and history display. |

The 24 rows are evenly split between 12 user and 12 assistant messages. All 12 assistant rows have a product payload; two users have chat history.

## Relationships and integrity checks

```text
catalogue.product_id 1 ────< inventory.product_id
users.id              1 ────< chat_messages.user_id
```

The schema declares both foreign keys with `ON UPDATE NO ACTION` and `ON DELETE NO ACTION`. `PRAGMA integrity_check` returned `ok`, and `PRAGMA foreign_key_check` returned no violations. The inspection connection reported `PRAGMA foreign_keys = 0`; SQLite foreign-key enforcement is per connection, so the MCP server must execute `PRAGMA foreign_keys = ON` when it opens each working-copy connection.

## Operational concepts and the three tickets

The requested concepts were searched by inspecting actual table names, column names, table DDL, and chat text. The supplied database contains no table or column for `ticket`, `status`, purchase order, vendor, invoice, customer order, payment, checking account/balance, facility, or obligation. No chat message contained those operational terms either.

| Business concept | Present in actual schema? | Evidence and implication |
| --- | --- | --- |
| Inventory levels | Yes | `inventory.quantity`, keyed by `product_id` and `size`; join to `catalogue` for product name and price. |
| Purchase orders | No | No matching table, column, or record exists. Cannot establish ordered, received, or backordered quantities. |
| Vendor invoices | No | No vendor, invoice, amount, due date, or payment-status fields exist. |
| Customer orders | No | No order header, line-item, fulfillment, or shipment table exists. |
| Payment information | No | No payment method, transaction, authorization, or settlement fields exist. `users` only stores account/authentication data. |
| Checking balances | No | No bank account, ledger, transaction, or balance table exists. |
| Facilities obligations | No | No facilities, lease, work-order, obligation, due-date, or maintenance table exists. |
| Ticket statuses | No | No ticket table or status column exists, and no chat record identifies a ticket. |

### Ticket 1

No ticket record or ticket description is present in the database or workspace. The required business decision cannot be identified from the supplied data. Depending on the missing ticket payload, it might require an inventory lookup, purchasing evidence, an order record, or a financial/operations record—but none may be assumed. Leave it unresolved until the authoritative ticket details are supplied.

### Ticket 2

No ticket record or ticket description is present. There is no database-supported decision to make, and there are no order, payment, checking, vendor, or invoice records from which to trace a resolution. Leave it unresolved pending the ticket source.

### Ticket 3

No ticket record or ticket description is present. There is no facilities/obligations or ticket-status data in this database, so an operational resolution cannot be justified. Leave it unresolved pending the assignment’s ticket payload or an additional supplied data source.

This is a data-availability finding, not a ticket resolution. The original and working databases were not modified.

## Agent and MCP implications for Problem 3

1. Configure the MCP server against `HW5/data/campus_customs_working.db`, not the original under HW4. Keep the original read-only and outside agent write paths.
2. Enable `PRAGMA foreign_keys = ON` per SQLite connection; the database declares foreign keys but the default inspection connection had enforcement disabled.
3. Parse `catalogue.colors`, `catalogue.search_tags`, and `chat_messages.products_json` as JSON text. They are not relational child tables.
4. Treat `inventory` as authoritative for product/size stock. Price and product identity come from `catalogue`; do not infer purchase orders or customer orders from inventory.
5. Exclude `users.password_hash`, passwords, tokens, and unnecessary account PII from tools, logs, agent context, and MCP responses.
6. Add bounded reads and, if operational search grows, indexes on the declared foreign-key columns (`inventory.product_id`, `chat_messages.user_id`). The current database is small, but only `inventory(product_id, size)` and primary/unique indexes were supplied.
7. Do not implement ticket-resolution tools until the three ticket records and the missing operational source tables/materials are supplied. The current schema cannot support those decisions.

## Problem 3 — MCP server architecture and tool contract

### Server and database boundary

`mcp_server.py` uses FastMCP 3.4.8 and the default stdio transport. An MCP host launches the file as a Python process; the server advertises exactly three tools. The fixed database path is `HW5/data/campus_customs_working.db`. The original `HW4/data/campus_customs.db` is never opened by the server.

Each tool opens a short-lived SQLite connection in read-only URI mode and enables `PRAGMA query_only = ON` and `PRAGMA foreign_keys = ON`. SQL values are bound parameters. Inputs are validated before queries, result sizes are bounded, and database failures return a structured `database_unavailable` error rather than SQL or filesystem details. There is no arbitrary query tool and no write capability.

### Initial tools

| Tool | Inputs | Structured success result | Workflow supported |
| --- | --- | --- | --- |
| `search_catalogue` | `query: str`; `limit: int = 8` (1–20); `in_stock_only: bool = false` | `ok`, normalized `query`, `in_stock_only`, and up to 20 `products`. Each product has `product_id`, `name`, `garment_type`, `price`, parsed `colors`, and aggregate `total_stock`. | Product discovery and inventory-aware catalogue investigation. It grounds an agent’s product question in `catalogue` plus summed `inventory`. |
| `check_inventory` | `product_id: str`; optional `size: str` | `ok`, product identity/name/type, `price`, parsed `colors`, `total_stock`, and size/quantity rows. | Exact availability questions such as “is this in stock in M?” It joins one `catalogue` product to its authoritative `inventory` rows. |
| `get_customer_chat_history` | `user_id: int`; `limit: int = 20` (1–100) | `ok`, `user_id`, and chronological `messages`. Each message has `message_id`, `role`, `content`, `created_at`, safe `product_ids`, `product_count`, and a JSON-payload validity flag. | Customer-service context from `chat_messages`. It does not claim to retrieve customer orders, payments, or ticket status because those tables do not exist. |

### Error contract

Every tool returns `ok: false` and an `error` object with `code` and `message` for expected business/input failures. Current codes include:

- `invalid_query`, `invalid_limit`, and `invalid_stock_filter` for catalogue search inputs.
- `invalid_product_id`, `product_not_found`, `invalid_size`, and `size_not_found` for inventory lookups.
- `invalid_user_id` and `user_not_found` for chat history.
- `database_unavailable` if the fixed working copy is missing or unreadable.

Messages do not include SQL, database paths, password hashes, email addresses, tokens, or raw `products_json`. Malformed JSON in catalogue colors is represented as an empty color list; malformed persisted chat product payloads are reported through `product_payload_valid: false` without failing the whole history request.

### Local protocol verification

`tests/test_mcp_server.py` launches `mcp_server.py` through FastMCP stdio and verifies:

- exactly `check_inventory`, `get_customer_chat_history`, and `search_catalogue` are advertised;
- an in-stock hoodie search returns four bounded results;
- `check_inventory("basic-hoodie-big-yale")` returns six sizes and total stock `60`;
- user `1` returns two requested chat messages;
- an unknown product returns `ok: false` with `product_not_found`.
- blank search input returns `invalid_query`, an injection-shaped product id returns `invalid_product_id`, and an unknown user returns `user_not_found`.

The test passed in `HW4/.venv` using FastMCP 3.4.8, MCP 1.30.0, Pydantic 2.13.5, and Python 3.13. The server’s database counts and product totals agree with the Problem 2 queries. Because the supplied schema has no ticket/order/purchasing/finance/facilities entities, these tools support grounded investigation only; the three ticket-specific workflows remain blocked pending the missing ticket source.

## Problem 4 — Coding-agent MCP integration

The project-level `.mcp.json` contains one server named `campus-customs`. It launches the absolute course-environment interpreter `HW4/.venv/Scripts/python.exe` with `mcp_server.py` as its argument and `HW5/` as its working directory. The only configured environment value is `PYTHONUNBUFFERED=1`; credentials are not needed by this local read-only server and are not present in the configuration.

`tests/run_mcp_smoke.py` loads that JSON configuration and uses `fastmcp.Client(config)` to perform the actual stdio MCP handshake and tool calls. It does not import `mcp_server.py` or reuse the server’s query helpers. Its independent comparisons use a separate SQLite read-only connection to the working database. The resulting structured evidence is in `output/mcp_smoke.json` with schema version `hw5.problem4.mcp_smoke.v1`.

The recorded run passed. Discovery returned exactly `check_inventory`, `get_customer_chat_history`, and `search_catalogue`. The normal cases were a four-result in-stock hoodie search, the six-size `basic-hoodie-big-yale` inventory lookup with 60 total units, and two chat messages for `user_id=1`; every result matched an independent query. The missing product returned `product_not_found`, and blank search input returned `invalid_query`, both matching independent validation/database checks.

The smoke evidence explicitly states that no ticket source was available. Therefore these calls are verified database workflows, not fabricated Ticket 101–103 outcomes. Problems 5–11 require the missing assignment/ticket and operational data before agent delegation, payment approval, dashboard, or final-reflection evidence can be produced.

