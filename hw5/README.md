# MGT 409 Homework 5 — Multi-Agent Operations for Campus Customs

## Current submission status

The operational data supplied in `data (1).zip` is now integrated. Problems 2–10 have working database, MCP, agent, API, dashboard, execution evidence, and reflection artifacts. Problem 11 is at the reproducible local-submission stage; no GitHub repository is claimed as published until an authenticated push succeeds.

Read [output/harness_operational.md](output/harness_operational.md) for the authoritative schema, agent boundaries, ticket findings, financial controls, and evidence map. The older catalogue-only material is retained and explicitly labeled as historical.

## Historical catalogue-only setup notes

The prior Campus Customs implementation is in `../HW4/`:

- `../HW4/data/campus_customs.db` — supplied SQLite database; it was inspected read-only and is excluded from Git by the HW5 ignore rules.
- `data/campus_customs_working.db` — byte-for-byte working copy used for Problem 2 inspection; experiments must use this copy, never the original.
- `../HW4/data/products/` — 102 supplied product JPGs used by the catalogue.
- `../HW4/backend/` — FastAPI, PydanticAI, SQLite tools, typed models, and the agent prompt.
- `../HW4/frontend/` — Vite + React + TypeScript storefront.
- `../HW4/output/harness.md` — documented database schema, API contract, agent contract, safety rules, limits, and run instructions.
- `../HW4/requirements.txt` and `../HW4/backend/requirements.txt` — Python dependencies; `../HW4/frontend/package.json` — front-end dependencies.
- `../HW4/AI_prompts.md` — prior homework’s prompt log and progression through its problems.

The database currently contains four application tables: `catalogue` (102 rows), `inventory` (612 rows), `users` (4 rows), and `chat_messages` (24 rows). It also has SQLite’s internal `sqlite_sequence` table. Password hashes and other account data were not copied into this documentation.

The schema does not contain operational ticket records or tables/columns for purchase orders, vendor invoices, customer orders, payment information, checking balances, facilities obligations, or ticket statuses. The three open tickets therefore cannot be identified or resolved from the supplied database alone; see `output/harness.md` for the evidence and the exact data dependency.

Other relevant course materials in the workspace include the HW3 product-identification agent and data pack, the HW2 harness and sales-agent materials, the root `HARNESS.md`, and the prior homework prompt logs. They remain in their existing homework folders; no files were copied into HW5.

## Intended structure as the assignment is supplied

The implementation folders can be added once the assignment defines the deliverables:

```text
HW5/
  AI_prompts.md
  README.md
  .gitignore
  backend/       # only if required by the assignment
  frontend/      # only if required by the assignment
  prompts/       # assignment-specific prompts
  data/          # local-only supplied data; never commit
  output/        # required evidence and reports
  tests/         # verification for the implemented problems
```

The supplied database remains in HW4 for now rather than being duplicated. If HW5 later needs a local copy, place it under an ignored `data/` directory and keep credentials in a local `.env` that is also ignored. Use the configured Portkey integration for OpenAI calls; never place `PORTKEY_API_KEY` in source, logs, reports, archives, or prompt documentation.

## Problem 2 status and readiness for Problem 3

Problem 2 has a working database copy, a schema/relationship reference, representative query findings, original-file verification, and an explicit inventory of missing operational concepts in `output/harness.md`. No ticket was modified or resolved.

Before Problem 3, configure the MCP server to open `data/campus_customs_working.db`, enable SQLite foreign-key enforcement on each connection, parse JSON stored in text fields, and block access to `users.password_hash`. The server also needs the missing ticket source or assignment payload before it can answer the three ticket questions.

## Problem 3 MCP server

Implementation files:

- `mcp_server.py` — FastMCP 3.4.8 stdio server with exactly three read-only tools.
- `requirements.txt` — FastMCP and Pydantic dependencies; SQLite comes from Python’s standard library.
- `tests/test_mcp_server.py` — stdio protocol smoke test that launches the server as a separate MCP process.

The server binds to `data/campus_customs_working.db` by code. It does not accept a database path from a caller, open the original HW4 database, expose SQL, or provide write tools. Each connection uses SQLite read-only mode plus `PRAGMA query_only = ON` and `PRAGMA foreign_keys = ON`. Tool responses use typed success/error envelopes with stable error codes.

Run it from `HW5/` with the existing course environment:

```powershell
..\HW4\.venv\Scripts\python.exe mcp_server.py
```

Run the protocol test with:

```powershell
..\HW4\.venv\Scripts\python.exe tests\test_mcp_server.py
```

The initial tools are `search_catalogue`, `check_inventory`, and `get_customer_chat_history`. They expose the useful business capabilities present in the actual database; none pretends to resolve the absent operational tickets.

## Problem 4 MCP integration

`.mcp.json` is the project configuration used by the coding-agent MCP client. It launches the verified course interpreter from `HW4/.venv`, runs `mcp_server.py` with `HW5/` as its working directory, and sets only `PYTHONUNBUFFERED`; no API key or database override is placed in the configuration.

The reproducible integration runner is `tests/run_mcp_smoke.py`. It loads `.mcp.json`, connects through the MCP protocol, discovers the advertised tool set, invokes all three tools, exercises missing-record and invalid-input paths, and independently compares the returned data with separate read-only SQLite queries. Evidence is stored in `output/mcp_smoke.json`.

The smoke run passed with exactly three advertised tools. All normal tool results matched independent database queries, and the expected `product_not_found` and `invalid_query` errors were returned. The evidence labels its inputs as representative database workflows because Ticket 101, 102, and 103 records are not present in the supplied workspace.

## Current operational implementation

### Data and safety

The authoritative database is `data/campus_customs_original.db`, copied into `data/campus_customs_working.db` for all agent and API activity. The working copy contains `tickets`, `inventory`, `pricing`, `vendors`, `invoices`, `leases`, `cash_accounts`, `payments`, plus app-owned `payment_requests` and `audit_events`. The original remains protected. Local `.db` files, the supplied zip, `.env`, and dependency folders are ignored by Git.

### Five-agent architecture

- Boss plans delegation, coordinates specialists, reconciles evidence, and makes the final structured decision.
- Inventory checks SKU/size/quantity/location and fulfillment feasibility.
- Accounting checks invoices, leases as financial obligations, cash, payment history, and pending requests.
- Facilities checks lease, space, landlord, and rent context.
- Customer Service checks requester context and produces truthful customer-facing next steps.

PydanticAI agents use the required `gpt-6-luna` model through Portkey's OpenAI-compatible Responses API. The key is loaded from a local ignored `.env`; `backend/agents.py` rejects a different `MODEL_NAME` rather than silently substituting another model. Each specialist receives only its role's MCP tools.

### MCP server and tools

`mcp_operational_server.py` is a FastMCP stdio server launched by `.mcp.json` with the course interpreter and the HW5 working directory. It exposes `inspect_ticket`, `check_inventory`, `inspect_financial_obligation`, `get_cash_balance`, and `prepare_payment_request`. Queries are parameterized and bounded. The first four are read-only; the last creates only a pending request and never moves money. `output/mcp_smoke.json` records protocol discovery and independent SQLite comparisons.

### FastAPI and approval boundary

Start the API with `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8051`. Routes list/detail tickets, run the actual Boss workflow, read audit events, read cash and payment requests, explicitly approve a pending payment, and reset the working copy. Approval uses a SQLite `BEGIN IMMEDIATE` transaction and checks pending state, ticket/obligation linkage, exact amount, duplicates, account existence, and sufficient funds before atomically inserting a payment and reducing cash. No agent or MCP tool can execute a payment.

### Frontend

From `frontend/`, run `npm install` once and `npm run dev -- --host 127.0.0.1 --port 5173`. The React/Vite dashboard reads tickets, events, cash, and payment requests from the API. It keeps “pending human approval” distinct from “executed,” confirms reset, disables duplicate actions, and includes loading, empty, and error states. Visual decisions are documented in `frontend/design.md`.

### Actual run outcomes

- Ticket 101: Boss → Inventory; size-S stock was 0, so the result was `needs_information` and no payment request.
- Ticket 102: Boss → Accounting; lease 1 rent was $2,400 with $3,400 checking, so pending request #1 was prepared. It remains unapproved; cash is unchanged.
- Ticket 103: Boss → Accounting → Inventory; only 8 of 20 medium hoodies were available and no payable obligation existed, so the result was `pending_approval` for pricing/sourcing review.

Current evidence is preserved in `output/audit_trail.json`, `output/backend_smoke.json`, `output/mcp_smoke.json`, and `output/desk_tickets.html`. The current working database has 97 audit events, zero executed payments, and one pending request. The reflection and ticket page explicitly distinguish observed results from any action that still requires human authorization.

### Verification commands

Run from `HW5/` with `..\HW4\.venv\Scripts\python.exe` (or an environment installed from `requirements.txt`):

```powershell
..\HW4\.venv\Scripts\python.exe -m compileall backend mcp_operational_server.py tests
..\HW4\.venv\Scripts\python.exe tests\run_backend_smoke.py
..\HW4\.venv\Scripts\python.exe tests\run_operational_smoke.py
```

The backend smoke test uses a temporary working database and makes no model calls. The operational MCP smoke test includes pending-request preparation, so preserve the existing evidence and use it as the recorded Problem 4/5 result unless you intentionally reset and rerun the operational workflow.

### GitHub publication

This folder is committed locally on `main` at commit `01af3b3`. GitHub CLI authentication was not available in the environment, so no remote or public URL is claimed. To publish it without exposing `.env` or course data:

```powershell
cd HW5
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

After the push, verify the public repository contains the 34 tracked source/evidence files and does not contain `data/`, `frontend/node_modules/`, `.env`, or API keys. Submit `https://github.com/YOUR-USERNAME/YOUR-REPOSITORY` on Canvas only after that verification.

