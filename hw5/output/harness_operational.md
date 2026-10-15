# HW5 operational harness reference

This is the authoritative harness for the supplied operational HW5 data. The older `harness.md` catalogue-only material is retained as historical Problem 2 evidence; it must not be used for the operational ticket workflow.

## Data boundary and reset rule

- Protected source: `data/campus_customs_original.db`
- Agent/API working copy: `data/campus_customs_working.db`
- The original is never opened by the MCP server and is never modified by reset or approval.
- `backend.db.ensure_runtime_schema()` adds only `payment_requests` and `audit_events` to the working copy.
- `POST /api/reset` copies the protected source over the working copy and recreates those app-owned tables.

The working database was reset before the recorded ticket runs. Its current evidence is: checking `$3,400.00`, tickets 101–103 open, zero executed payments, one pending payment request for Ticket 102, and 97 audit events. The pending request is intentionally not approved.

## Operational schema discovered from SQLite

| Table | Purpose and important fields | Relationships and agent use |
| --- | --- | --- |
| `tickets` | Operational work queue: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`. | `lease_id` points to `leases.id`; `invoice_id` points to `invoices.id`. Boss starts here and preserves the ticket status until evidence supports a change. |
| `inventory` | SKU/size stock: `sku`, `name`, `size`, `qty`, `location`. | Joined by `sku` to ticket demand; Inventory uses it to test exact fulfillment. |
| `pricing` | `sku`, `unit_cost`, `list_price`. | Joined by SKU for margin and discount decisions. |
| `vendors` | Vendor master data: `id`, `name`, `specialty`, `lead_days`. | Joined by `invoices.vendor_id`; Accounting uses it to understand an invoice obligation. |
| `invoices` | Payable obligation: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`. | Vendor foreign key; an invoice can support a payment request only while open/due. |
| `leases` | Facilities obligation: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`. | Ticket 102 references lease 1; Facilities and Accounting verify it. |
| `cash_accounts` | Current cash: `name`, `balance`, `date`. | `checking` is the approval guardrail; approval must leave a non-negative balance. |
| `payments` | Executed money movement: `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`. | Duplicate checks use kind/ref/account; only the API approval transaction inserts rows. |
| `payment_requests` | App-owned pending/approved request: ticket and obligation reference, amount, account, reason, requester, status, approval fields. | MCP can prepare a pending request; it cannot execute it. |
| `audit_events` | Durable event log: `run_id`, `ticket_id`, `agent`, `event_type`, `details_json`, `created_at`. | Reconstructs delegation, MCP calls/results, reports, decisions, payment requests, approvals, resets, and errors. |

The operational database has foreign keys for ticket references and agent connections enable `PRAGMA foreign_keys=ON`. All SQL values are bound parameters. There is no unrestricted SQL tool.

## Ticket decisions

### Ticket 101 — Bulldog tee

Tauhid Zaman requests one `CC-TEE-WHITE`, size S. Ticket 101 links to invoice 501, but that reference does not prove the customer order can be fulfilled or that payment should be made. The Inventory specialist was the correct first consultation. `inspect_ticket` and `check_inventory` found size S quantity `0` in Aisle B, with unit cost `$8` and list price `$28`. Boss returned `needs_information`: ask whether the customer wants another size or prefers to wait. No payment request was prepared.

### Ticket 102 — Rent due

Elm City Properties sent a rent notice for the Chapel Street shop. Ticket 102 links to lease 1, which records `$2,400` due 2026-09-02. Accounting was the correct first specialist. It verified no prior payment, checking `$3,400`, and prepared payment request #1. The request remains `pending`; no payment row was inserted, no cash moved, and the ticket remains open. A human must explicitly approve it before execution.

### Ticket 103 — Bulk hoodie discount

Yale AI Club asks for 20 `CC-HOOD-NAVY` hoodies in size M and a bulk discount. Accounting checked pricing (`$22` cost, `$58` list) and found no payable obligation; Inventory then found only 8 units in size M, 12 short. Boss returned `pending_approval` for human pricing/sourcing review. No discount, fulfillment promise, or payment request was created.

## MCP contract

`mcp_operational_server.py` uses FastMCP over stdio and the fixed working database. It advertises exactly:

- `inspect_ticket(ticket_id)` — ticket plus related inventory, pricing, invoice/lease, cash, payments, and payment requests.
- `check_inventory(sku, size?)` — exact stock and pricing for a SKU/size.
- `inspect_financial_obligation(ticket_id)` — linked invoice or lease, cash accounts, existing payments, and requests.
- `get_cash_balance(account='checking')` — read-only cash balance.
- `prepare_payment_request(ticket_id, requested_by, reason)` — creates/reuses a pending request only for an open ticket with a legitimate open/due obligation; never changes cash or inserts a payment.

Each tool returns a typed `{ok, error}` envelope. Invalid IDs, missing tickets, invalid SKUs, missing obligations, duplicate payments, and unavailable databases receive stable error codes. `users.password_hash` and unrelated catalogue-only data are not exposed.

## Agent architecture

PydanticAI creates five distinct roles:

- Boss plans the smallest sufficient delegation, coordinates specialists, reconciles evidence, and chooses `resolved`, `needs_information`, `blocked`, or `pending_approval`.
- Inventory owns stock, size, location, pricing, and fulfillment feasibility. It receives `inspect_ticket` and `check_inventory`.
- Accounting owns invoices, leases as financial obligations, cash, payment history, and request preparation decisions. It receives `inspect_ticket`, `inspect_financial_obligation`, and `get_cash_balance`.
- Facilities owns lease/space and rent context. It receives `inspect_ticket` and `inspect_financial_obligation`.
- Customer Service owns requester context and truthful customer-facing next steps. It receives `inspect_ticket` and `check_inventory`.

Tool calls go through one FastMCP client per workflow and are recorded before and after invocation. Specialists receive only their allowed tool functions; they do not share an unrestricted tool menu.

Portkey is used through `OpenAIResponsesModel` at `https://api.portkey.ai/v1` with `x-portkey-provider: openai` and the required `gpt-6-luna` model. The key is loaded from a local ignored `.env`; no key is stored in source, evidence, or logs.

## Financial safety

Preparing a request and executing a payment are separate operations. The approval route uses a SQLite `BEGIN IMMEDIATE` transaction, checks pending status, ticket/obligation linkage, exact obligation amount, duplicate payments, account existence, and sufficient funds, then inserts the payment, updates cash, marks the invoice paid when relevant, marks the request approved, and resolves the ticket atomically. Failed approvals roll back. The dashboard labels pending requests and requires an approver name.

## FastAPI and frontend

The backend is `backend/main.py`. Routes include ticket list/detail, real Boss workflow runs, in-memory run lookup, persisted audit filtering, cash, payment-request listing, explicit approval, health, and reset. The React/Vite dashboard is under `frontend/`; it reads all operational state from the API, shows events and payment controls, and does not hard-code ticket outcomes. See `README.md` for commands and `frontend/design.md` for the visual rationale.

## Verification evidence

- `output/mcp_smoke.json` records the real MCP protocol discovery and tool results checked against independent SQLite queries. Payment preparation was tested as pending only.
- `output/backend_smoke.json` is an offline API test against a temporary database copy. It covers health, tickets, invalid IDs, cash, approval success, duplicate approval, insufficient funds, reset, and post-reset financial consistency. It records that the protected original hash was unchanged and that no model calls were made.
- `output/audit_trail.json` is an export of the preserved working-database audit events and current financial state.
- `output/desk_tickets.html` contains the expected plans, actual ticket outcomes, cash reconciliation, and reflection notes grounded in the recorded run.
