import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["COPILOT_MOCK"] = "1"


@pytest.fixture(autouse=True)
def fresh_state(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    yield
