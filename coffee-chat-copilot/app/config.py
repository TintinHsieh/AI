"""Settings + .env loading.

The .env file is searched in this order (first value wins):
  1. the app folder (coffee-chat-copilot/.env)
  2. the repo root (one level up)
  3. the folder above the repo (where the teaching staff keep their .env)
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
STATE_DIR = Path(os.getenv("COPILOT_STATE_DIR", DATA_DIR / "state"))

ENV_CANDIDATES = [APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"]
for _p in ENV_CANDIDATES:
    if _p.is_file():
        load_dotenv(_p, override=False)

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
COURSE_MODEL = "gpt-6-luna"

# USD per 1M tokens (course pricing table, gpt-6-luna)
PRICES = {
    "gpt-6-luna": {"input": 0.10, "cached": 0.01, "cache_write": 0.125, "output": 0.50},
    "gpt-6.1-sol": {"input": 2.00, "cached": 0.10, "cache_write": 2.50, "output": 10.00},
}


@dataclass
class Settings:
    provider: str
    api_key: str | None
    base_url: str | None
    model: str
    daily_token_budget: int
    run_token_budget: int
    max_llm_calls_per_run: int
    max_runs_per_minute: int
    max_email_chars: int
    reasoning_effort: str
    use_cache: bool


def load_settings() -> Settings:
    portkey = os.getenv("PORTKEY_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    force_mock = os.getenv("COPILOT_MOCK", "").strip() == "1"
    if force_mock or not (portkey or openai_key):
        provider, key, base, model = "mock", None, None, COURSE_MODEL
    elif portkey:
        # Course rule: only gpt-6-luna on the course key.
        provider, key, base, model = "portkey", portkey, PORTKEY_BASE_URL, COURSE_MODEL
    else:
        provider, key, base, model = "openai", openai_key, None, os.getenv("OPENAI_MODEL", COURSE_MODEL)
    return Settings(
        provider=provider,
        api_key=key,
        base_url=base,
        model=model,
        daily_token_budget=int(os.getenv("DAILY_TOKEN_BUDGET", "400000")),
        run_token_budget=int(os.getenv("RUN_TOKEN_BUDGET", "60000")),
        max_llm_calls_per_run=int(os.getenv("MAX_LLM_CALLS_PER_RUN", "10")),
        max_runs_per_minute=int(os.getenv("MAX_RUNS_PER_MINUTE", "8")),
        max_email_chars=int(os.getenv("MAX_EMAIL_CHARS", "6000")),
        reasoning_effort=os.getenv("REASONING_EFFORT", "low"),
        use_cache=os.getenv("USE_PROMPT_CACHE", "1") != "0",
    )
