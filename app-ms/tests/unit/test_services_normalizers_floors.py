from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Resolve project root so imports like 'from services.normalizers import ...' work
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.normalizers import parse_floors, render_floors  # type: ignore  # noqa: E402


def _cfg() -> dict:
    return {
        "floor": {
            "drop_tokens": ["этаж", "эт", "э."],
            "map_special": {
                "basement": ["подвал", "-1"],
                "socle": ["цоколь"],
                "mezzanine": ["мезонин"],
            },
            "multi": {
                "enabled": True,
                "split_separators": [",", ";", "/", " и ", "&"],
                "range_separators": ["-", "–"],
                "render": {
                    "join_token": "; ",
                    "range_dash": "–",
                    "sort_numeric_first": True,
                    "uniq": True,
                },
            },
        }
    }


def _render(val: object) -> str:
    cfg = _cfg()
    return render_floors(parse_floors(val, cfg), cfg)


def test_basic_ranges_and_separators():
    assert _render("1 и 2") == "1–2"
    assert _render("1,3;5") == "1; 3; 5"
    assert _render("цоколь/1-2") == "1–2; цоколь"
    # reversed range normalizes
    assert _render("3-1") == "1–3"


def test_drop_tokens_and_spaces():
    assert _render("1 этаж, 2 эт, 3 э.") == "1–3"


def test_special_mapping_basement_and_mix():
    assert parse_floors("-1", _cfg()) == ["подвал"]
    assert _render("подвал") == "подвал"
    # mixed with numeric
    assert _render("-1/1") == "1; подвал"


def test_uniqueness_and_ordering():
    assert _render("2,1,2,мезонин,мезонин") == "1–2; мезонин"


def test_list_input_and_empty():
    cfg = _cfg()
    floors = parse_floors(["1", "2-3", "цоколь"], cfg)
    assert render_floors(floors, cfg) == "1–3; цоколь"

    assert parse_floors(None, cfg) == []
    assert render_floors([], cfg) == ""

