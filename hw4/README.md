# Campus Customs / HW4

Campus Customs is a Yale spiritwear storefront with a Vite + React + TypeScript front end, a FastAPI backend, and a Portkey-backed PydanticAI shop assistant. The assistant searches the local catalogue, reports database-backed price and inventory facts, and returns structured product matches that the website renders as cards.

## Repository-safe data setup

The supplied data pack is intentionally local-only and is excluded by `.gitignore`. After cloning this repository, place the files here:

```text
hw4/
  data/
    campus_customs.db
    products/
      ...catalogue image files...
```

Do not commit the database, product images, a data zip, or a real `.env` file. Copy `.env.example` to `.env` and put a valid local `PORTKEY_API_KEY` there before using chat. The products, authentication, and non-AI routes can still be inspected after the data pack is installed.

## Backend

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The equivalent command from inside `backend/` is:

```text
uvicorn main:app --reload
```

The backend exposes `/api/health`, product and image routes, authentication routes, chat, and authenticated chat history. It reads `data/campus_customs.db` and `data/products/` at runtime; it does not copy those files into source code.

## Front end

In a second terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`. The default API URL is `http://localhost:8000`; set `VITE_API_URL` in a local frontend environment file if the backend runs elsewhere. To verify a production bundle:

```text
npm run build
```

## Agent layout

The requested four agent files live together under `backend/`:

- `backend/prompts/prompt.md` - grounding, privacy, and safety instructions.
- `backend/agent.py` - Portkey/PydanticAI model wiring, tools, usage limits, and audit events.
- `backend/tools.py` - bounded, read-only SQLite catalogue and inventory tools.
- `backend/models.py` - typed requests, replies, product matches, stock, and history records.

`output/harness.md` documents the database fields, model fields, tools, safety rules, limits, audit format, and run commands. `output/app_check.html` links to the live-site evidence screenshots. `output/audit_trail.json` is append-only across local runs and contains short, redacted activity summaries.

## Public-repository checklist

The tracked project should include the application source, prompts, documentation, and `.env.example`. The following must remain untracked and local: `.env`, `data/campus_customs.db`, `data/products/`, `data*.zip`, `.venv/`, `frontend/node_modules/`, and `frontend/dist/`.
