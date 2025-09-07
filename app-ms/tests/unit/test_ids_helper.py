from __future__ import annotations

import sys
from pathlib import Path

# Resolve project root
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.ids_helper import listing_id  # type: ignore  # noqa: E402


def test_listing_id_changes_with_area_and_floors():
    rules = {
        "identifier": {
            "listing_id": {
                "compose_parts": [
                    "object_id",
                    "building_token_slug",
                    "use_type_norm_slug",
                    "floors_norm_slug",
                    "area_1dp",
                ],
                "hash_len": 8,
                "join_token": "__",
            }
        }
    }
    core_base = {
        "object_name": "Объект",
        "building_raw": "стр. 1",
        "use_type_norm": "офис",
        "floors_norm": "1",
        "area_sqm": 10.0,
    }
    lid1 = listing_id(core_base, rules, source_file="fileA.pdf")

    core_diff_area = {**core_base, "area_sqm": 10.5}
    lid2 = listing_id(core_diff_area, rules, source_file="fileA.pdf")

    core_diff_floor = {**core_base, "floors_norm": "1–2"}
    lid3 = listing_id(core_diff_floor, rules, source_file="fileA.pdf")

    assert lid1 != lid2 != lid3


def test_listing_id_without_building_token():
    rules = {
        "identifier": {
            "listing_id": {
                "compose_parts": ["object_id", "building_token_slug", "area_1dp"],
                "hash_len": 8,
            }
        }
    }
    core = {
        "object_name": "Комета",
        "building_raw": None,
        "area_sqm": 12.0,
        "use_type_norm": None,
        "floors_norm": None,
    }
    lid = listing_id(core, rules, source_file="source.pdf")
    assert lid.startswith("kometa__") or lid.endswith("__")

