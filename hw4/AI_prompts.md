# AI Prompts

This file records the prompts used with the vibe coder, one problem at a time. No application implementation has started yet; follow-up entries should be expanded with the exact wording used during development.

## Problem 1 — Vibe Coder Prompts

### Prompt typed

> Create `AI_prompts.md` at the start of the assignment and keep it updated as we work. Include one section for every problem, with the problem number and title, at least one prompt in my own words, and a follow-up prompt when one is needed. Do not build the application until I ask you to.

### Follow-up prompt

Not needed yet.

### What was lacking after the first prompt

Nothing was lacking for this setup step; the prompt log was created before application work began.

## Problem 2 — Analyze the Database

### Prompt typed

> Inspect `data/campus_customs.db` and document every application table in `output/harness.md`, including at least `catalogue`, `inventory`, and `users`. List each field and briefly explain why it matters to the shop or chatbot. Do not modify application behavior yet.

### Follow-up prompt

Not needed; the first pass covered all four application tables and their relationships. If a later schema check finds a missed field, use:

> Recheck the database schema and sample rows, then correct `output/harness.md` so every field in the three required tables is covered without guessing.

### What was lacking after the first prompt

Nothing was lacking after the first prompt; the supplied database was inspected and `output/harness.md` was started with the table fields, row counts, relationships, and field purposes.

## Problem 3 — Build the Campus Customs Website

### Prompt typed

> Build the React, Vite, and TypeScript Campus Customs storefront with navigation for Home, Products, About Us, Log in, and Create account. Load catalogue products and images from a small FastAPI backend, add product detail pages with sizes and stock, and include a bottom-right chat stub. Use original collegiate-store wording and the project’s black-and-pink visual direction, and work only on Problem 3.

### Follow-up prompt

> The first frontend build is missing React type declarations. Add the standard React and React DOM type packages, rerun the TypeScript/Vite production build, and then smoke-test the FastAPI health, product search, product detail, and image endpoints.

> Test the main navigation, product cards, product detail route, image loading, and chat stub, then fix only the Problem 3 gaps you find.

### What was lacking after the first prompt

The first pass omitted `@types/react` and `@types/react-dom`, so TypeScript could not type-check the JSX; after that follow-up, the frontend build and database-backed API checks completed successfully.

## Problem 4 — Create Account and Login

### Prompt typed

> Add create-account and login flows using first name, last name, email, and password. Store new users in the database with secure password hashing, support the seeded test user, and verify both a test login and a newly created account. Document the auth design in `output/harness.md`.

### Follow-up prompt

> The first pass only has placeholder auth forms. Add real register and login API calls, use a salted one-way password hash, return a signed session token without exposing password data, and verify the seeded account plus a new synthetic account end to end.

> Test the seeded account and a newly registered account end to end, check that plaintext passwords are never stored, and fix any auth or documentation issue you find.

### What was lacking after the first prompt

The first pass had placeholder forms with no database or API connection; the follow-up added the auth endpoints, secure password storage, browser session handling, and end-to-end checks.

## Problem 5 — PydanticAI Agent Backend

### Prompt typed

> Build the FastAPI chatbot backend around a PydanticAI agent. Keep the system prompt in `backend/prompts/prompt.md`, wiring in `backend/agent.py`, tools in `backend/tools.py`, and structured types in `backend/models.py`. Add a chat route and connect it to the front-end chat widget using the configured Portkey-backed model.

### Follow-up prompt

Use this follow-up after the initial route is present:

> Start the backend with Uvicorn, send a representative chat request, inspect the structured response and errors, then fix the smallest Problem 5 issue without starting later problems. Keep the agent split across the requested four files and do not expose the Portkey key.

### What was lacking after the first prompt

The first pass created the requested PydanticAI files and route but still needed verification of tool registration and the frontend API connection; the follow-up led to those checks and the structured `ChatResponse` contract.

## Problem 6 — Title Not Included in Supplied Assignment Text

### Prompt typed

> The supplied assignment text jumps from Problem 5 to Problem 7 and does not include a Problem 6 title or requirements. Do not invent the missing task; identify the authoritative Problem 6 requirements before implementing it.

### Follow-up prompt

> Please provide the complete Problem 6 title and requirements, then update this section and work only on that problem.

### What was lacking after the first prompt

The supplied assignment text lacks both the Problem 6 title and its requirements.

## Problem 7 — Chat Search That Updates the Page

### Prompt typed

> Extend the agent so catalogue questions such as “What hoodies do you have?” return structured product matches. Render those matches as dynamic product cards with image, name, price, and short information, and ensure every dynamically added card still opens the existing product detail view. Document the API path in `backend/prompts/prompt.md` and `output/harness.md`.

### Follow-up prompt

Use this follow-up to verify the visible contract:

> Test a category question from the chat widget, verify that the returned cards are rendered from structured matches, and click a returned card to confirm the normal detail view still works. Also make plural questions such as "what hoodies do you have?" match the catalogue's singular garment labels.

### What was lacking after the first prompt

The first pass returned agent matches through the API but left the old local chat stub in the visible site; the follow-up connected the widget, added the dynamic product-card tray, preserved shared detail navigation, and fixed plural hoodie search.

## Problem 8 — Customer Memory

### Prompt typed

> For logged-in shoppers, persist chat history in an appropriate database table and reload it on return. Pass the shopper’s name and email to the agent, include current product-page context for questions such as “Do you have this in pink?”, and keep guest chat available without requiring persistence. Document the storage and context flow in `output/harness.md`.

### Follow-up prompt

Use this follow-up to verify persistence and context:

> Log in as the seeded test user, send a chat turn, reload the chat, and verify the user and assistant rows plus structured product matches are restored from `chat_messages`. Also test guest chat and a product-page question such as "do you have this in pink?"; fix any persistence, identity, or context issue and document the final flow in `output/harness.md`.

### What was lacking after the first prompt

The first pass had no authenticated history route or frontend reload, so it needed a transactional `chat_messages` write, a bearer-protected history read, user identity in agent dependencies, and route/product context in each chat request.

## Problem 9 — Usability Improvements

### Prompt typed

> Add two front-end usability improvements and two agent or backend usability improvements. Before or during implementation, write `output/usability.md` with what each improvement does and why it helps a shopper or the business, then verify that all four improvements appear in the running app.

### Follow-up prompt

> Review the saved-piece controls, catalogue sort/reset controls, inventory-aware agent search, and repeated-search cache. Run the frontend build and direct backend checks, then update `output/usability.md` so each claim matches the implementation.

### What was lacking after the first prompt

The first prompt defined the four improvements but did not choose concrete features. The follow-up selected two visible catalogue improvements and two backend retrieval improvements, implemented all four, and verified their code paths and build.

## Problem 10 — Style the Website

### Prompt typed

> Give the Campus Customs site a creative storefront design with thoughtful fonts, color, hierarchy, motion, product presentation, and chat styling. Keep the experience coherent with the black-and-pink project style, and write a short concrete explanation in `output/design.md`.

### Follow-up prompt

> Inspect the running pages at desktop and narrow widths, improve the most visible hierarchy or interaction problems, and update `output/design.md` to match the changes. Verify that the motion has a reduced-motion fallback and that the chat still feels usable.

### What was lacking after the first prompt

The first pass already had a strong black-and-pink foundation but needed a more distinctive lookbook layer, richer product metadata, more intentional motion, and a branded chat treatment. The follow-up direction was incorporated into the design pass and its concrete rationale in `output/design.md`.

## Problem 11 — Site Testing (App Check)

### Prompt typed

> Test the live site and create `output/app_check.html` with a heading, screenshot, and one or two sentence caption for three checks: honest inventory and price from the database, dynamic search-result cards after a category question, and one Problem 9 usability feature. Store the images in `output/app_check_images/` and link them with relative paths.

### Follow-up prompt

Not needed yet; use this if any evidence is unclear or unlinked:

> Open `output/app_check.html`, verify all three screenshots load through relative paths, and retake or recaption any image that does not clearly prove the required behavior.

### What was lacking after the first prompt

The first pass needed the running API and front end to be exercised together so the evidence would show actual database values and rendered structured matches. The completed check now includes `output/app_check.html` with three linked screenshots: the Basic Hoodie Big Yale inventory detail, the hoodie chat search tray, and the Problem 9 saved-pieces filter.

## Problem 12 — Audit Trail, Safety, Finish Harness

### Prompt typed

> Add an append-only `output/audit_trail.json` recording agent-loop time, tool name, short arguments or result, and stop reason. Add practical safety rules to `backend/prompts/prompt.md`, then finish `output/harness.md` with models, tools, safety rules, loop limits, result caps, model choices, and run instructions.

### Follow-up prompt

> Run a representative agent interaction, confirm a new audit event is appended rather than overwriting prior events, and check that the finished harness explains every required system component and run command.

I used this follow-up to verify both a real provider-error path and a deterministic offline completion path, then checked that the previous audit events remained in the JSON array.

### What was lacking after the first prompt

The first pass had not yet wired the agent-loop events into a persistent file or documented the typed contract and runtime limits. The completed pass adds privacy-preserving append-only audit events, explicit prompt safety rules, PydanticAI request/tool budgets, and a full Problem 12 section in `output/harness.md` covering models, tools, caps, model selection, and run commands.

## Problem 13 — Push to GitHub and Submit the URL

### Prompt typed

> Prepare the `hw4` project for a public GitHub repository with the required front-end, backend, prompt, output, README, dependency, and environment-example files. Add `.gitignore` rules so the real `.env`, database, and product images are excluded, explain how to run both servers, and verify the final file tree before pushing.

### Follow-up prompt

Not needed yet; use this only after the project is complete:

> Check the repository contents and Git status for secrets, the database, and product images, confirm `.env.example` contains placeholders only, then push the clean project and record the public repository URL.

### What was lacking after the first prompt

The project has not been built, audited for excluded files, committed, or pushed yet.
