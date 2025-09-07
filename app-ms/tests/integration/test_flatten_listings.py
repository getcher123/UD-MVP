from __future__ import annotations

import sys
from pathlib import Path


# Resolve project root so imports work
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.listings import flatten_objects_to_listings  # type: ignore  # noqa: E402
from core.config_loader import get_rules  # type: ignore  # noqa: E402


def test_flatten_minimal_json_two_listings():
    rules = get_rules(str(root / "config" / "defaults.yml"))
    objects = [
        {
            "object_name": "Объект",
            "buildings": [
                {
                    "building_name": "стр. 1",
                    "listings": [
                        {"floor": "1", "area_sqm": 100, "use_type": "офис", "rent_rate": 12000.0, "rent_vat": "не применяется"},
                        {"floor": "1-2", "area_sqm": 50, "use_type": "office", "rent_rate": 18000.0, "rent_vat": "не применяется"},
                    ],
                }
            ],
        }
    ]

    rows = flatten_objects_to_listings(objects, rules, request_id="rid", source_file="file.pdf")
    assert len(rows) == 2

    # listing ids unique
    ids = {r["listing_id"] for r in rows}
    assert len(ids) == 2

    # building name and floors
    assert all(r["building_name"] == "Объект, стр. 1" for r in rows)
    floors = {r["floors_norm"] for r in rows}
    assert floors == {"1", "1–2"}

    # rate base should equal rent_rate if VAT not applied
    for r in rows:
        assert r["rent_rate_year_sqm_base"] in (12000.0, 18000.0)

