# Evidence checklist (do these on your laptop, about 1 hour total)

Every rubric row gives full credit only with **proof from the real app**. These steps produce it.
Commands are for Windows PowerShell (macOS/Linux: use `source .venv/bin/activate`).

## 0. Setup (5 min)
```powershell
cd "C:\Users\User\Desktop\Yale SOM\Coursework\AI Foundation\Final Project"
git clone https://github.com/TintinHsieh/AI.git
cd AI\coffee-chat-copilot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then open .env and paste your PORTKEY_API_KEY
python -m pytest -q         # 26 passed
python run.py               # opens http://127.0.0.1:8000 — the badge should say "Live: gpt-6-luna via portkey"
```
In **Settings**: put in your real name, signature, phone, email, Zoom details, and **your real class schedule**.
(These are saved in `data/state/`, which git ignores. They never go to GitHub.)

## 1. Tokenomics + "did cost cutting hurt?" (10 min, about $0.05 of tokens)
```powershell
python scripts/evaluate.py                    # shipped settings
python scripts/evaluate.py --effort medium    # more reasoning: better quality? higher cost?
python scripts/evaluate.py --no-cache         # what caching saves
```

## 2. Safety evidence (3 min)
```powershell
python scripts/red_team.py
```

## 3. Screenshots of a real run (5 min)
Keep `python run.py` running. In a second terminal:
```powershell
pip install playwright
python -m playwright install chromium
python scripts/capture_screenshots.py
```
(Click **Reset demo data** in the app first for a clean run.) Also take your own screenshots of anything you like.

## 4. Impact: the part only you can do (30 min)
Fill in `docs/evidence/impact.json`:
1. **Your baseline.** Take 3 real banker emails from this season. Time yourself replying *the old way*
   (Outlook template + calendar + TrainTime + Maps). Then time the same 3 with the app (paste → review → copy).
2. **Season volume.** Count the coffee chat emails in your Sent folder this recruiting season.
3. **Past mistakes.** How many times did you offer a slot that clashed with something?
4. **A real user.** Ask one classmate who is recruiting for IB to try it for 15 minutes on one of their real
   emails. Write down their before and after minutes and a one-sentence quote, and screenshot it if you can.
   This is the Tier 3 evidence.

## 5. Build the report + slides (1 min)
```powershell
python scripts/build_docs.py      # -> docs/report.html and docs/slides.html, every image embedded
```
Open both by double-clicking. Search for **TODO** (yellow): each one is missing evidence.
Read every sentence and make sure it matches what your app actually did. You're responsible for every word.

## 6. Submit
- Commit and push (`git add -A; git commit -m "evidence"; git push`). Never commit `.env`.
- Dry run: clone the repo into a new folder, put `.env` ONE folder above it, follow the README, and confirm the app runs.
- Canvas: repo link, `docs/report.html`, `docs/slides.html` (+ optional 2–3 min demo video).
