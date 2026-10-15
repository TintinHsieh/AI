# AI Prompts — MGT 409 Homework 5

## Assignment and logging status

This log records only prompts actually supplied in this conversation. It preserves the substance of the request and does not invent problem work, follow-ups, or corrections.

The workspace did not contain the complete HW5 assignment, an assignment PDF/Markdown/Word file, or HW5 starter files. Therefore the official titles for Problems 1–11 cannot be transcribed yet. The placeholder wording below is deliberate and should be replaced with the official title as soon as the authoritative assignment is supplied.

### Later data-file correction

The user subsequently supplied `HW5/data/data (1).zip`, which contained the authoritative operational database. The implementation history below preserves the initial catalogue-only findings and then records the correction: the operational working/original copies were created, the five-agent workflow and supporting API/UI were built against the new schema, and real model runs were performed only after the data was available. No assignment document with official Problem 1–11 titles was supplied, so those titles remain explicitly marked as unavailable rather than invented.

## Cross-problem setup request

### Prompt typed

> We're completing MGT 409 Homework 5, Multi-Agent Operations for Campus Customs. First, read the complete HW5 assignment, all provided starter files, and the current project directory so you understand the required deliverables and how the problems build on one another.
>
> Create an AI_prompts.md file in the HW5 project folder to document the AI-assisted development process across Problems 1–11. Organize it by problem number and official assignment title. For each problem, record the actual prompts I give you, any follow-up requests or corrections, and a brief explanation of what changed. Preserve the substance of my requests rather than inventing prompts or claiming work that didn't happen.
>
> Also establish a clean project structure, identify the supplied database and other course materials, and note any dependencies needed later. Do not implement future problems yet. Make sure credentials, environment variables, virtual environments, and other private configuration files are excluded from Git.
>
> At the end, tell me what you found in the assignment, how the homework is organized, and what is ready for Problem 2.

### Follow-up requests or corrections

None recorded yet.

### What changed

The HW5 folder was prepared with this prompt log, a setup README, and a `.gitignore` that excludes local secrets, environment files, virtual environments, databases, supplied data packs, dependencies, build output, and logs. No Problem 1–11 implementation was created. The setup review found the prior Campus Customs source and database in `HW4`, but no HW5 assignment or starter bundle.

## Problem 1 — Official assignment title not available in workspace

### Prompt typed

No Problem 1-specific prompt has been supplied in this conversation. The cross-problem setup request above is not being relabeled as a Problem 1 implementation request.

### Follow-up requests or corrections

None recorded.

### What changed

No Problem 1 work was performed. The official title and requirements are pending the authoritative HW5 assignment.

## Problem 2 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 2 by thoroughly inspecting the provided Campus Customs database and understanding how it supports the business operations described in the assignment.
>
> Locate the original database and create the required working copy so that experiments and agent operations do not modify the original course data. Inspect the complete database schema, including tables, columns, primary keys, foreign keys, relationships, relevant constraints, and representative records.
>
> Identify the three open operational tickets and trace the information needed to resolve each one. Explain which records and tables contain inventory levels, purchase orders, vendor invoices, customer orders, payment information, checking balances, facilities obligations, and ticket statuses, wherever those concepts exist in the actual schema. Do not assume table or column names; discover them from the database.
>
> Create or update the project's harness documentation with a useful database reference: each table's purpose, its important fields, its relationships, and why it matters to the agents. Include a clear explanation of the three open tickets and the business decisions each one requires.
>
> Verify that the working database is readable, that the original remains untouched, and that your descriptions agree with actual database queries. Preserve the original data and avoid prematurely resolving tickets.
>
> Finish with the database findings, relevant file paths, and any issues that could affect the MCP server in Problem 3.

### Follow-up requests or corrections

None recorded.

### What changed

The first inspection copied `HW4/data/campus_customs.db` byte-for-byte and correctly documented the catalogue-only schema without inventing tickets. After the user supplied `data (1).zip`, the authoritative operational database was copied to `data/campus_customs_original.db` and `data/campus_customs_working.db`. The operational schema, relationships, representative records, three tickets, cash, obligations, and safety rules are documented in `output/harness_operational.md`. The original remains protected and the working database is the only agent/API write target.

## Problem 3 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 3 by building a functional Model Context Protocol (MCP) server that gives AI agents controlled access to the Campus Customs working database.
>
> Use the database schema and three open tickets analyzed in Problem 2 to determine the three most useful initial MCP tools. The tools should expose meaningful business capabilities that agents need to investigate or resolve those tickets, rather than arbitrary SQL access. Design their names, arguments, return values, and error handling around actual business questions.
>
> Implement the MCP server using the appropriate Python MCP framework and the required course environment. Use the working database only, with safe parameterized queries, validation of inputs, structured tool results, and clear handling of missing or invalid records. Avoid giving agents unrestricted database write access.
>
> Ensure the server can start reliably and advertise its tools through the MCP protocol. Document what each tool does, its input parameters, its output structure, and which ticket or workflow it supports.
>
> Update the harness and README with the server architecture, database connection, tool descriptions, and instructions for running it. Include any dependencies in the project requirements.
>
> Test the server locally to verify it starts, connects to the correct database, exposes exactly the intended initial tools, and returns accurate results. Do not fabricate successful tool responses. Report the implementation files, tool definitions, and test outcomes.

### Follow-up requests or corrections

None recorded.

### What changed

The initial catalogue-only implementation was `mcp_server.py` with three read-only tools. Once the operational data arrived, the authoritative server became `mcp_operational_server.py` with five bounded tools: `inspect_ticket`, `check_inventory`, `inspect_financial_obligation`, `get_cash_balance`, and `prepare_payment_request`. It uses parameterized SQL, typed envelopes, the working copy only, and a separate approval boundary for executed payments. `output/mcp_smoke.json` preserves the operational protocol evidence.

## Problem 4 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 4 by integrating the MCP server from Problem 3 into the coding-agent environment and proving that the tools work through the MCP connection.
>
> Create or update the project's .mcp.json configuration using the correct executable, arguments, working directory, and environment setup for the actual project. The configuration should allow the coding agent to discover and invoke the MCP server's tools without manually executing database queries.
>
> Start the MCP server, confirm that all three tools are discoverable, and call each tool with realistic inputs derived from the three Campus Customs tickets. Include normal cases and relevant error or edge cases.
>
> For every test, record the tool name, arguments, returned result, and whether the result matches an independently checked database query. Save structured evidence in output/mcp_smoke.json using the format required by the assignment, or a clear equivalent if the assignment specifies a different schema.
>
> Investigate and correct any connection failures, tool schema mismatches, incorrect SQL results, serialization errors, or environment issues. Retest after fixes.
>
> Update the README and harness to explain how MCP integration works and how someone can reproduce the smoke tests.
>
> Do not proceed until the MCP tools work through the actual protocol and their results have been verified against the database. Summarize the real test results and any remaining limitations.

### Follow-up requests or corrections

None recorded.

### What changed

The first `.mcp.json` integration launched the catalogue-only server and its three-tool smoke test. After the operational data arrived, the configuration was updated to launch `mcp_operational_server.py`; `tests/run_operational_smoke.py` verified discovery of all five operational tools, normal and error cases, and independent SQLite comparisons. The recorded evidence is in `output/mcp_smoke.json`. A pending-payment preparation case was tested without executing money movement.

## Problem 5 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 5 by building the multi-agent operations system for Campus Customs using PydanticAI and the required gpt-6-luna model through Portkey.
>
> Implement five distinct agents: Boss, Inventory, Accounting, Facilities, and Customer Service. Give each agent a clearly defined responsibility, appropriate system instructions, access to relevant MCP tools, and a mechanism for communicating or delegating work.
>
> The Boss agent should coordinate the workflow, interpret an incoming ticket, decide which specialist should investigate first, delegate tasks as necessary, combine specialist findings, and determine the next business action. Specialist agents should focus on their own responsibilities rather than all behaving as interchangeable general assistants.
>
> Expand the MCP server with any additional narrowly scoped tools needed to resolve the three tickets safely. The tools should support real operations such as checking inventory, examining invoices, reviewing cash balances, finding orders, and preparing authorized actions, depending on the actual database schema and assignment requirements.
>
> Implement real delegation and tool execution, not hard-coded responses that merely simulate a conversation between agents. Use Pydantic models or equivalent structured outputs where appropriate. Handle invalid inputs, unavailable records, tool failures, and inconsistent business information.
>
> Introduce a persistent audit trail that records agent identities, delegations, tool calls, tool results, decisions, and significant workflow events. The logs should allow someone to reconstruct what happened during each ticket.
>
> Ensure payments are not automatically executed just because an agent recommends them. Agents may investigate and prepare payment requests, but actual payment execution must be controlled by a separate authorization mechanism.
>
> Use the correct Portkey configuration and API interface for the required model. Read credentials from a local ignored environment file, never hard-code secrets, and do not silently substitute another model.
>
> Update the harness, README, requirements, and relevant architecture documentation. Run meaningful integration tests and demonstrate that the agents can coordinate through the real MCP tools. Preserve the original database and existing evidence.

### Follow-up requests or corrections

None recorded.

### What changed

Initially blocked for the same missing-data reason recorded above. After `data (1).zip` arrived, implemented `backend/agents.py` with Boss, Inventory, Accounting, Facilities, and Customer Service using PydanticAI, Portkey's Responses API, structured Pydantic outputs, real MCP calls, delegation events, and persistent audit logging. Specialists now receive role-specific tools. Agents prepare payment requests but cannot execute them. Real runs for Tickets 101–103 are preserved in the audit trail.

## Problem 6 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 6 by creating the ticket planning and comparison interface before executing the final three-ticket workflow.
>
> Build output/desk_tickets.html as a readable, self-contained HTML document with separate sections or tabs for Tickets 101, 102, and 103, plus Cash and Reflection sections. Follow any specific layout or content requirements in the assignment.
>
> For each ticket, inspect the actual database records and describe the operational issue in business terms. Then document the expected agent workflow: which specialist the Boss should consult first, what information that specialist needs, which additional agents should be involved, what MCP tools should be called, what evidence would support the decision, and what the appropriate outcome should be under the business rules.
>
> Distinguish clearly between the expected plan and the actual outcome. The expected sections must be written before the final agent runs, and the actual sections should remain empty or explicitly pending until Problem 9.
>
> Plan the financial implications of each ticket, including any payments that might be requested, whether human approval would be required, and how checking cash could change. Do not assume a payment should be made simply because a ticket involves an invoice.
>
> Include placeholders for the final cash reconciliation, screenshots or evidence, and reflection. Make the page easy to read, navigate, and update.
>
> Verify that the plans are consistent with the database and the assignment. Do not fabricate actual agent runs or resolved ticket outcomes. Report the generated HTML file and briefly explain the expected workflow for each ticket.

### Follow-up requests or corrections

None recorded.

### What changed

Initially blocked pending the operational data. After the data arrived, created `output/desk_tickets.html` with separate Ticket 101–103, Cash, and Reflection sections. Expected plans were grounded in the operational records before the preserved real runs; Actual sections now report only observed agent outcomes, with pending human-approval items clearly labeled.

## Problem 7 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 7 by implementing a functional FastAPI backend that connects the Campus Customs database, MCP tools, multi-agent system, and future dashboard.
>
> Create backend/main.py and any supporting modules needed for a maintainable API. Implement the routes required by the assignment for listing and inspecting tickets, initiating an agent run, retrieving agent activity and audit events, checking the current cash balance, approving pending payments, and resetting the working database.
>
> The ticket-run route must invoke the actual Boss agent and its specialists rather than return canned outputs. Capture and expose meaningful events such as delegations, tool calls, decisions, payment requests, and errors so the frontend can display what happened.
>
> Implement a strict separation between preparing a payment and executing it. An agent can recommend or prepare a payment request, but money should move only through the explicit approval endpoint. Validate that the payment is pending, has not already been executed, corresponds to a legitimate obligation, and will not make the checking balance negative.
>
> Implement a safe reset mechanism that restores the working database to the intended initial state without modifying the original supplied database. Reset behavior must be explicit and verifiable.
>
> Provide appropriate CORS configuration for the local frontend, consistent response schemas, startup instructions, and dependency declarations.
>
> Test every route with actual database records, including successful requests and important failure cases. Confirm that checking balances and payment records remain consistent. Document the API in the README and explain the approval safety design in the harness.

### Follow-up requests or corrections

None recorded.

### What changed

Initially blocked pending data. After the data arrived, implemented `backend/main.py`, `backend/db.py`, and `backend/audit.py` with ticket, run, audit, cash, payment-request, explicit approval, health, and reset routes. Approval uses a transaction and validates obligation, duplicate, exact amount, and available cash. The agent-run route calls the real workflow; it is not a canned result.

## Problem 8 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 8 by creating a polished, functional React and Vite dashboard in frontend/ for the Campus Customs multi-agent operations system.
>
> The frontend must communicate with the real FastAPI backend from Problem 7. It should display the three operational tickets, allow the user to select a ticket and initiate an agent run, show the sequence of agent activities and delegations, display tool results and final decisions, and provide clear controls for reviewing and approving pending payments.
>
> Include a prominent checking-balance display that updates from the backend after relevant operations. Show payment amounts, approval status, ticket status, and any useful operational details. Make it obvious when an action is pending human approval versus already completed.
>
> Design the dashboard to make a multi-agent workflow understandable to someone who did not build the system. Use readable typography, clear navigation, distinct status indicators, consistent spacing, and responsive layouts. Include loading states, empty states, API error handling, and safeguards against accidental duplicate actions.
>
> Create design.md explaining the visual design, layout, information hierarchy, and user experience choices. Ensure the interface meets any specific assignment requirements.
>
> Do not hard-code the three ticket outcomes or fake backend events. All operational data must come from the API. Where live streaming is unavailable, use a reliable supported method such as polling to show progress.
>
> Run the frontend and backend together, test the complete interaction flow, and verify that the browser can fetch tickets, run agents, display events, approve a payment, and refresh the cash balance.
>
> Fix build errors, broken API calls, and misleading UI states. Provide the final run instructions and the locations of the frontend, backend, and design documentation.

### Follow-up requests or corrections

None recorded.

### What changed

Initially blocked pending the API and operational records. After implementation, created the React/Vite dashboard under `frontend/`, with live API reads for tickets, events, cash, and requests; loading, empty, error, and duplicate-action safeguards; and `frontend/design.md`. The UI does not hard-code ticket outcomes.

## Problem 9 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 9 by executing the full Campus Customs workflow on Tickets 101, 102, and 103 using the real multi-agent system, MCP tools, FastAPI backend, and dashboard built in the earlier problems.
>
> Begin by inspecting the assignment’s required execution and evidence rules. Reset the working database to its original intended state and record the starting cash balance and the initial status of each ticket.
>
> Run each of the three tickets through the actual Boss agent. Allow it to delegate to the appropriate specialists and use the real MCP tools. Capture the full sequence of agent decisions, tool calls, delegations, payment requests, and outcomes in the audit trail.
>
> When an agent prepares a legitimate payment request, execute it only through the required explicit human-approval mechanism. Do not silently auto-approve payments or bypass the approval endpoint. Stop for my approval if a real authorization decision is required.
>
> After each ticket, verify the database state, ticket status, payment records, and checking balance. Confirm that no payment is duplicated, no unauthorized payment is executed, and the cash balance remains valid.
>
> Update output/desk_tickets.html with the Actual results for each ticket, including which agents participated, what tools they used, how the real workflow compared with the expected plan, what decisions were made, and what ultimately happened.
>
> Complete the Cash section using actual starting cash, approved payments, and ending cash. Reconcile the amounts against the database and audit records. Capture the screenshots or other evidence required by the assignment and save them in the correct locations.
>
> If model-tool compatibility problems occur, fix the underlying integration rather than substituting fabricated agent outputs. Use the required model and appropriate Portkey API interface.
>
> Preserve all original run evidence. Report the actual outcomes, any deviations from the plan, the final cash balance, and any unresolved issues. Do not copy another student’s ticket results or force the system to produce predetermined outcomes.

### Follow-up requests or corrections

None recorded.

### What changed

After the operational data arrived, reset the working database, recorded starting cash of `$3,400`, and ran Tickets 101, 102, and 103 through the real Boss workflow using Portkey/PydanticAI and MCP. Ticket 101 returned `needs_information` after size-S stock was zero; Ticket 102 created pending request #1 for `$2,400` rent; Ticket 103 returned `pending_approval` after 8 available versus 20 requested. No human authorization was supplied, so no payment was executed. The current database has 97 audit events, open tickets, zero payments, and the one pending request. `output/audit_trail.json` and `output/desk_tickets.html` preserve the evidence.

## Problem 10 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 10 by writing a substantive reflection based entirely on the real execution evidence from Problem 9.
>
> Review the three ticket plans, actual agent runs, audit trail, tool calls, dashboard interactions, payment approvals, database changes, and cash reconciliation. Use those records to evaluate how well the multi-agent system performed.
>
> For each ticket, compare Expected versus Actual. Explain whether the Boss delegated appropriately, whether each specialist contributed useful information, whether MCP tools supplied accurate evidence, whether the final decision was justified, and whether the workflow was efficient. Assign and explain a performance grade for each ticket using the assignment’s required grading approach.
>
> Analyze whether a single general-purpose agent could have handled the same work effectively. Discuss the practical benefits and costs of multiple specialized agents, including coordination, tool access, error isolation, complexity, token usage, and oversight.
>
> Identify additional operational problems this team could reasonably solve with its current tools and architecture. Also identify problems it cannot safely or reliably solve without additional data, integrations, tools, or human authority.
>
> Discuss the role of human approval in financial decisions, what the audit trail made visible, what surprised you during execution, and what you would improve if you continued developing the system.
>
> Write the reflection in clear, natural student language rather than generic promotional language about AI. Use concrete examples from the actual ticket runs, including failures or limitations. Do not invent events or claim the agents succeeded at tasks that were not demonstrated.
>
> Insert the final reflection into the Reflection tab of output/desk_tickets.html and update any other required reflection deliverable. Verify that the narrative matches the audit logs and actual financial results.

### Follow-up requests or corrections

None recorded.

### What changed

The reflection is grounded in the preserved runs and database state. It compares Expected versus Actual for each ticket, grades the three outcomes, evaluates specialist coordination and MCP evidence, discusses single-agent tradeoffs and human approval, and identifies demonstrated limits. Because the pending rent request was not authorized, the page does not claim an approval or post-payment cash change.

## Problem 11 — Official assignment title not available in workspace

### Prompt typed

> Complete HW5 Problem 11 by preparing the entire Campus Customs multi-agent operations project for a clean, reproducible public GitHub submission.
>
> Read the complete assignment submission requirements and inspect the HW5 project folder. Preserve all required source code, database files permitted by the assignment, MCP configuration, agent implementation, backend, frontend, design documentation, harness, ticket dashboard, reflection, screenshots, audit logs, and other required evidence.
>
> Finalize AI_prompts.md so it accurately records the prompts and meaningful follow-ups for Problems 1–11. Use my actual requests and development history. Do not fabricate verbatim prompts, testing activity, or work that was not performed.
>
> Write a clear README explaining the project, its five-agent architecture, the MCP server and tools, how the agents delegate, the human-approval design, and the main outcomes. Include instructions for installing dependencies, configuring environment variables, starting the MCP server, running the FastAPI backend, launching the React frontend, and reproducing the relevant tests.
>
> Create or verify .env.example with placeholder values only. Ensure .gitignore excludes the real .env, API keys, virtual environments, dependency folders, caches, and temporary files. Scan all files that would be committed for credentials and other sensitive information.
>
> Perform a final verification of the repository. Check that Python modules import, frontend builds, required outputs exist, internal file links work, and documented commands are consistent with the code. Prefer offline verification and do not rerun costly model calls or overwrite original evidence unnecessarily.
>
> Remove redundant temporary artifacts only when they are not required and are safely preserved elsewhere. Do not delete the original audit trail, ticket results, or evidence merely to make the repository look cleaner.
>
> Create or connect a public GitHub repository under my own account, commit the finished HW5 project, and push the main branch if authentication is available. Verify that the published repository contains the expected files and does not expose credentials.
>
> If GitHub authentication is unavailable, stop at the authenticated step and provide exact instructions for me to finish the push locally. Do not request that I paste a personal access token into chat.
>
> Finish with the repository URL, a summary of what was actually verified, any unresolved issues, and the exact URL I should submit on Canvas. Do not claim the repository is published until the push has succeeded.

### Follow-up requests or corrections

None recorded.

### What changed

The local submission package is finalized: operational database copies, MCP configuration/server, five-agent implementation, FastAPI backend, React/Vite frontend, design and harness documentation, prompt log, ticket dashboard, audit export, MCP evidence, backend smoke evidence, and ignored-secret configuration are present. Requirements and run instructions were updated, and `.gitignore` excludes `.env`, keys, databases, virtual environments, dependency folders, caches, and logs. GitHub publication was not claimed; it remains pending authenticated repository creation/push.

