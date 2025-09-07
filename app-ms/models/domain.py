from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ExtractionResult:
    rows: List[Dict[str, Any]]

