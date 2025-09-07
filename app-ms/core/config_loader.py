from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _read_sequence_from_yaml(path: Path, key: str) -> List[str] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    lines = text.splitlines()
    seq: List[str] = []
    inside = False
    base_indent = None
    for ln in lines:
        if not inside and f"{key}:" in ln:
            inside = True
            base_indent = len(ln) - len(ln.lstrip())
            continue
        if inside:
            if ln.strip().startswith("-"):
                val = ln.split("-", 1)[1].strip()
                seq.append(val)
            else:
                if ln.strip() == "" or (len(ln) - len(ln.lstrip())) <= (base_indent or 0):
                    break
    return seq or None


def get_rules(rules_path: str | Path) -> Dict[str, Any]:
    """Load aggregation/normalization rules.

    YAML-free, dependency-free loader that extracts building_columns and
    supplies sane defaults for other sections used by the pipeline.
    """
    p = Path(rules_path)
    building_columns = _read_sequence_from_yaml(p, "building_columns") or [
        "building_id",
        "building_name",
        "object_id",
        "object_name",
        "use_type_set_norm",
        "fitout_condition_mode",
        "delivery_date_earliest",
        "floors_covered_norm",
        "area_sqm_total",
        "listing_count",
        "rent_rate_year_sqm_base_min",
        "rent_rate_year_sqm_base_avg",
        "rent_rate_year_sqm_base_max",
        "rent_vat_norm_mode",
        "opex_year_per_sqm_avg",
        "rent_month_total_gross_avg",
        "sale_price_per_sqm_min",
        "sale_price_per_sqm_avg",
        "sale_price_per_sqm_max",
        "sale_vat_norm_mode",
        "source_files",
        "request_id",
        "quality_flags",
    ]

    listing_columns = _read_sequence_from_yaml(p, "listing_columns") or [
        "listing_id",
        "object_id",
        "object_name",
        "building_id",
        "building_name",
        "use_type_norm",
        "area_sqm",
        "divisible_from_sqm",
        "floors_norm",
        "market_type",
        "fitout_condition_norm",
        "delivery_date_norm",
        "rent_rate_year_sqm_base",
        "rent_vat_norm",
        "opex_year_per_sqm",
        "opex_included",
        "rent_month_total_gross",
        "sale_price_per_sqm",
        "sale_vat_norm",
        "source_file",
        "request_id",
        "quality_flags",
    ]

    return {
        "aggregation": {
            "building": {
                "name": {"compose": "{object_name}{suffix}"},
                "source_files": {"unique_join": " | "},
            }
        },
        "normalization": {
            "use_type": {"canon": ["офис", "торговое", "псн", "склад"], "synonyms": {"офис": ["office", "open space"], "торговое": ["retail", "street-retail"], "псн": ["psn"], "склад": ["storage", "warehouse"]}},
            "fitout_condition": {"canon": ["с отделкой", "под отделку"], "synonyms": {"с отделкой": ["готово к въезду", "с мебелью", "есть отделка"], "под отделку": ["white box", "готово к отделке"]}},
            "vat": {"treat_not_applied": ["усн", "упрощенка", "ндс 5%"]},
            "floor": {
                "drop_tokens": ["этаж", "эт", "э."],
                "map_special": {"basement": ["подвал", "-1"], "socle": ["цоколь"], "mezzanine": ["мезонин"]},
                "multi": {
                    "enabled": True,
                    "split_separators": [",", ";", "/", " и ", "&"],
                    "range_separators": ["-", "–"],
                    "render": {"join_token": "; ", "range_dash": "–", "sort_numeric_first": True, "uniq": True},
                },
            },
        },
        "derivation": {
            "rent_rate_year_sqm_base": {
                "priority": ["direct", "reconstruct_from_month"],
                "reconstruct_from_month": {"respect_vat": True, "respect_opex": True, "vat_fallback": 0.2, "round_decimals": 2},
            },
            "gross_month_total": {"round_decimals": 2},
        },
        "output": {"building_columns": building_columns, "listing_columns": listing_columns},
        "quality": {"outliers": {"rent_rate_year_sqm_base": {"min": 1000, "max": 200000}}},
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
        },
    }


__all__ = ["get_rules"]
