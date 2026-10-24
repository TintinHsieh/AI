# ☕ Coffee Chat Copilot

**An AI agent app that runs the investment banking coffee chat process for Yale SOM students.** Reach out after a
corporate presentation, answer bankers inside the finance club's 15-minute rule, offer 90-minute windows that really
work around classes **and** the Metro-North ride to Grand Central, plan the NYC day across several banks, send the
club-format invite, the running-late note, and the thank-you. It also keeps an eye on you: meals, treats,
friends, and sleep.

> Final project, MGT 409 AI Foundations for Managers (Fall 2026).

## Run it (about 3 minutes)

Requires **Python 3.10+**. Commands work in Windows PowerShell, macOS, and Linux.

```bash
git clone <this repo>
cd <repo>/coffee-chat-copilot
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

The app opens at **http://127.0.0.1:8000**.

**API key.** The app looks for a `.env` file in this folder, then the repo root, then **the folder above the repo**
(where the teaching staff keep theirs). It uses `PORTKEY_API_KEY` (course key, model `gpt-6-luna`) or
`OPENAI_API_KEY`. See `.env.example`. With no key it starts in **Demo mode** (badge bottom-left): every feature
works with a scripted stand-in for the model and estimated token counts.

## A 2-minute tour

1. **Inbox → Reach out.** Banker *Priya Raman*, bank *Goldman Sachs*, met at *Goldman Sachs Corporate
   Presentation*, referred by *Henry Liu*, format *In-person or virtual* → **Draft outreach**. You get the club's
   outreach email with three 90-minute windows. Each window fits your classes, and at least one also works for an NYC trip.
   All three are put **on hold** so no other banker gets them. Click **Mark as sent**.
2. **Paste the banker's reply** in the thread, e.g. *"Friday 10/30 at 10:30 AM works, come by our office."* The
   copilot matches it to your hold and drafts the **in-person invite**, with a **15-minute countdown**. Mark as sent:
   the chat is confirmed and the other two holds are released.
3. **NYC Day Planner**: leave campus 7:17, Metro-North #1505, subway 29 min to 200 West St, chat, train home,
   food and treat suggestions.
4. **Inbox → Banker emailed → sample "Injection Attack"**: the guard flags it, and the reply contains only safe,
   validated content.
5. **Usage & Cost**: tokens per email (input / cached / output), cost per email, per user per month, and at scale.
6. **Settings**: your classes, signature, Zoom details, and the club's 11 email templates.

## How it works

| Agent | Job | Tools |
|---|---|---|
| **Intake** | Reads a banker's email → who, bank, request type, in-person/virtual, availability, picked time, introductions, suspicious content (JSON schema output) | none |
| **Scheduler** | Picks three 90-minute windows that respect the banker's availability | `find_open_slots`, `check_slot`, `get_trains`, `travel_time` (read-only) |
| **Responder** | Fills the right club template (11 templates) word for word; writes thank-you specifics from your notes | none |
| **Wellbeing Coach** | Turns the week's load into 3 kind, specific nudges | none (gets facts from code) |

Plain Python does everything that must be exact: free/busy, trains, travel times, holds, the NYC itinerary,
re-validating every time the AI proposes, draft checking, budgets. **The model can't invent a time and can't book
anything.** See `docs/` for the full report.

## Safety

- Prompt-injection scanner, plus the banker's email is wrapped as untrusted data.
- Agents only see free/busy, never class names; tools are read-only; holds are written by code.
- **Draft checker** blocks any time or date that wasn't validated, class names, other banks, and secrets → retry → template fallback.
- Loop guard (6 scheduler steps, duplicate-call detection), max 10 model calls / 60k tokens per email,
  400k tokens per day, 8 runs per minute (all configurable in `.env`).
- Nothing is ever sent automatically. You copy the draft into Outlook.

## Tests and evidence

```bash
python -m pytest -q                       # 26 tests, demo mode, no key needed
python scripts/evaluate.py                # real token counts, cost, latency, quality checks -> docs/evidence/
python scripts/evaluate.py --effort medium   # does spending more help?
python scripts/evaluate.py --no-cache        # what does prompt caching save?
python scripts/red_team.py                # 8 injection / exfiltration attacks -> docs/evidence/
```

## Data

- `data/profile.json`: placeholder student profile and sample SOM schedule. **Edit it in Settings**; your edits are
  saved in `data/state/` (git-ignored), so your phone, email, and Zoom link never get committed.
- `data/templates/*.md`: the finance club's Outlook templates (outreach, follow-up, invites, running late, thank-yous).
- `data/metro_north_sample.csv`: a **sample** New Haven Line timetable modeled on real service. For the real
  schedule, download the MTA Metro-North GTFS zip and run `python scripts/update_timetable_from_gtfs.py <zip>`.
- `data/bank_offices.json`: NYC offices of 20 banks (approximate coordinates for travel estimates).
- `data/sample_emails/`: test emails, including an injection attack.
