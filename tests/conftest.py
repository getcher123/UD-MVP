from __future__ import annotations

import sys
from pathlib import Path


# Ensure the microservice code (app-ms) is importable as a top-level package path
ROOT = Path(__file__).resolve().parent.parent
APP_MS_DIR = ROOT / "app-ms"

for p in (ROOT, APP_MS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
