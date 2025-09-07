from __future__ import annotations

from pathlib import Path
import sys

root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.derivation import derive_all  # type: ignore  # noqa: E402
from core.config_loader import get_rules  # type: ignore  # noqa: E402


def test_derive_all_direct_and_gross():
    rules = get_rules(str(root / "config" / "defaults.yml"))
    listing = {
        "area_sqm": 100.0,
        "rent_rate": 12000.0,
        "rent_vat": "не применяется",
        "opex_included": False,
        "opex_year_per_sqm": 0.0,
    }
    out = derive_all(listing, rules)
    assert out["rent_rate_year_sqm_base"] == 12000.0
    # gross month without VAT and opex
    assert round(out["rent_month_total_gross"], 2) == round(12000 * 100 / 12, 2)

