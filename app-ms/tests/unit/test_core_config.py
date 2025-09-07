from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest


root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from core.config import get_settings  # type: ignore  # noqa: E402


def test_defaults_and_rule_path_exists(monkeypatch: pytest.MonkeyPatch):
    # Clear env
    for k in ("RULES_PATH", "DEFAULT_QUERY_PATH", "RESULTS_DIR"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()  # type: ignore[attr-defined]
    s = get_settings()
    assert Path(s.RULES_PATH).exists()
    assert Path(s.DEFAULT_QUERY_PATH).exists()

