from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from core.config_loader import get_rules  # type: ignore
from services.normalizers import normalize_listing_core  # type: ignore


def _load_rules() -> dict:
    return get_rules(str(root / "config" / "defaults.yml"))


def test_normalize_listing_core_basic() -> None:
    rules = _load_rules()
    src = {
        "use_type": "office",
        "area_sqm": "100,0",
        "floor": "1-2",
        "fitout_condition": "готово к въезду",
    }
    parent = {"object_name": "БЦ", "building_name": "ул. Ленина, 1"}
    core = normalize_listing_core(src, parent, rules)
    assert core["object_name"] == "БЦ"
    assert core["building_token"]
    assert core["use_type_norm"] == "офис"
    assert core["area_sqm"] == 100
    assert core["floors_norm"] == "1–2"
    assert core["fitout_condition_norm"] == "с отделкой"


def test_divisible_from_sqm_falls_back_to_area() -> None:
    rules = _load_rules()
    src = {"area_sqm": 87, "divisible_from_sqm": None}
    parent: dict = {}
    result = normalize_listing_core(src, parent, rules)
    assert result["divisible_from_sqm"] == 87


def test_divisible_from_sqm_preserves_explicit_value() -> None:
    rules = _load_rules()
    src = {"area_sqm": 87, "divisible_from_sqm": "40"}
    parent: dict = {}
    result = normalize_listing_core(src, parent, rules)
    assert result["divisible_from_sqm"] == 40


def test_opex_included_falls_back_when_year_present() -> None:
    rules = _load_rules()
    src = {"opex_year_per_sqm": "1500", "opex_included": None}
    parent: dict = {}
    result = normalize_listing_core(src, parent, rules)
    assert result["opex_included"] == "не включен"
    assert result["opex_year_per_sqm"] == 1500.0


def test_opex_included_respects_explicit_value() -> None:
    rules = _load_rules()
    src = {"opex_year_per_sqm": "1500", "opex_included": "включен"}
    parent: dict = {}
    result = normalize_listing_core(src, parent, rules)
    assert result["opex_included"] == "включен"
