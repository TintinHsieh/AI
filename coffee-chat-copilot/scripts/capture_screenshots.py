"""Drive the running app through a real end-to-end run and save screenshots for the report.

Setup once:   pip install playwright && python -m playwright install chromium
Then:         python run.py            (in one terminal, with your key in .env)
              python scripts/capture_screenshots.py      (in another terminal)

Uses whatever data is in the app. Click "Reset demo data" first for a clean run.
Saves PNGs to docs/screenshots/.
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TIMEOUT = 120_000  # real model calls can take a while


async def act(pg, sel, path):
    """Click and wait until the app's API call for it has finished."""
    async with pg.expect_response(lambda r: path in r.url and r.request.method == "POST", timeout=TIMEOUT):
        await pg.click(sel)
    await pg.wait_for_timeout(1200)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        pg = await b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(URL)
        await pg.wait_for_timeout(1000)
        shot = lambda name, full=True: pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full)

        # 1. outreach after a corporate presentation
        await pg.click("#compose-seg button[data-c=outreach]")
        await pg.fill("#o-name", "Priya Raman")
        await pg.select_option("#o-bank", "Goldman Sachs")
        await pg.fill("#o-event", "Goldman Sachs Corporate Presentation")
        await pg.fill("#o-ref", "Henry Liu")
        await act(pg, "#btn-outreach", "/api/outreach")
        await pg.click(".convo details summary >> nth=0")
        await shot("01_outreach")
        await pg.click("[data-sent]")
        await pg.wait_for_timeout(800)

        # 2. banker picks the window that also works in person
        opt = await pg.evaluate("fetch('/api/threads').then(r=>r.json()).then(t=>{const s=t[0].steps[t[0].steps.length-1];return s.options.find(o=>o.offer_mode==='either')||s.options[0]})")
        d = datetime.fromisoformat(opt["start"])
        reply = (f"Hi,\n\nThanks for reaching out, great to meet you last week. {d.strftime('%A')} {d.month}/{d.day} at "
                 f"{d.strftime('%I:%M %p').lstrip('0')} works for me. Come by our office at 200 West St and we can grab a coffee downstairs.\n\n"
                 "Best,\nPriya Raman\nAssociate, Investment Banking Division\nGoldman Sachs")
        await pg.fill("#nx-reply", reply)
        await act(pg, "#nx-reply-go", "/api/inbox")
        await pg.click(".convo details summary >> nth=0")
        await pg.wait_for_timeout(400)
        await shot("02_invite_with_trace")
        await pg.click("[data-sent]")
        await pg.wait_for_timeout(800)

        # 3. a banker who reaches out first with constraints
        await pg.click("#compose-seg button[data-c=email]")
        await pg.click("#sample-list button:has-text('Evercore Virtual')")
        await act(pg, "#btn-draft", "/api/inbox")
        await pg.click(".convo details summary >> nth=0")
        await shot("03_banker_first_with_trace")

        # 4. prompt injection
        await pg.click("#sample-list button:has-text('Injection Attack')")
        await act(pg, "#btn-draft", "/api/inbox")
        await pg.click(".convo details summary >> nth=0")
        await shot("04_injection_blocked")

        # 5. introduction
        await pg.click("#sample-list button:has-text('Intro')")
        await act(pg, "#btn-draft", "/api/inbox")
        await shot("05_intro")

        # 6. second in-person bank so the NYC day has two stops
        await pg.click("#sample-list button:has-text('Lazard In Person')")
        await act(pg, "#btn-draft", "/api/inbox")

        for tab, name in [("calendar", "06_calendar"), ("nyc", "07_nyc_day"), ("usage", "09_usage")]:
            await pg.click(f"button[data-tab={tab}]")
            await pg.wait_for_timeout(1200)
            if tab == "calendar":
                await pg.click("#cal-next")
                await pg.wait_for_timeout(800)
            await shot(name)
        await pg.click("button[data-tab=wellbeing]")
        await pg.wait_for_timeout(600)
        await pg.click("#coach-ai")
        await pg.wait_for_timeout(8000)
        await shot("08_wellbeing")
        await pg.click("button[data-tab=settings]")
        await pg.wait_for_timeout(800)
        await shot("10_settings")
        await b.close()
    print(f"Saved screenshots to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
