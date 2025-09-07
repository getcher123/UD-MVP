from __future__ import annotations

from pathlib import Path
import sys

root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.normalizers import normalize_listing_core  # type: ignore  # noqa: E402
from core.config_loader import get_rules  # type: ignore  # noqa: E402


def test_normalize_listing_core_basic():
    rules = get_rules(str(root / "config" / "defaults.yml"))
    src = {"use_type": "office", "area_sqm": "100,0", "floor": "1-2", "fitout_condition": "готово к въезду"}
    parent = {"object_name": "Объект", "building_name": "стр. 1"}
    core = normalize_listing_core(src, parent, rules)
    assert core["object_name"] == "Объект"
    assert core["building_token"] in ("стр. 1", "стр. 1")
    assert core["use_type_norm"] == "офис"
    assert core["area_sqm"] == 100.0
    assert core["floors_norm"] == "1–2"
    assert core["fitout_condition_norm"] == "с отделкой"

