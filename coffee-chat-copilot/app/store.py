"""Tiny JSON-file storage for threads, holds, check-ins, and usage logs."""
import json
import threading
import uuid
from pathlib import Path

from . import config

_lock = threading.Lock()


def _path(name: str) -> Path:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    return config.STATE_DIR / name


def load(name: str, default):
    p = _path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save(name: str, value) -> None:
    with _lock:
        p = _path(name)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        tmp.replace(p)


def append_jsonl(name: str, record: dict) -> None:
    with _lock:
        with _path(name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")


def read_jsonl(name: str) -> list[dict]:
    p = _path(name)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def load_profile() -> dict:
    custom = _path("profile.json")
    src = custom if custom.exists() else config.DATA_DIR / "profile.json"
    return json.loads(src.read_text(encoding="utf-8"))


def save_profile(profile: dict) -> None:
    save("profile.json", profile)


TEMPLATE_KEYS = ["availability_reply", "outreach_intro", "outreach_no_intro", "follow_up_no_response", "time_conflict",
                 "invite_virtual", "invite_in_person", "running_late", "thank_you_post_chat", "thank_you_post_event",
                 "thank_you_for_intro"]


def load_templates() -> dict:
    """Club templates: data/templates/*.md, overridden by edits saved in the state folder."""
    out = {}
    for key in TEMPLATE_KEYS:
        custom = _path("templates") / f"{key}.md"
        src = custom if custom.exists() else config.DATA_DIR / "templates" / f"{key}.md"
        out[key] = src.read_text(encoding="utf-8")
    return out


def save_template(key: str, text: str) -> None:
    if key not in TEMPLATE_KEYS:
        raise KeyError(key)
    with _lock:
        d = _path("templates")
        d.mkdir(exist_ok=True)
        (d / f"{key}.md").write_text(text, encoding="utf-8")
