from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # add app-ms root

from services.aggregate_buildings import group_to_buildings
from services.excel_export import build_xlsx
from utils.fs import build_result_path, write_bytes


def _read_building_columns_from_yaml(path: Path) -> List[str] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    lines = text.splitlines()
    cols: List[str] = []
    inside = False
    base_indent = None
    for ln in lines:
        if not inside and "building_columns:" in ln:
            inside = True
            base_indent = len(ln) - len(ln.lstrip())
            continue
        if inside:
            if ln.strip().startswith("-"):
                val = ln.split("-", 1)[1].strip()
                cols.append(val)
            else:
                if ln.strip() == "" or (len(ln) - len(ln.lstrip())) <= (base_indent or 0):
                    break
    return cols or None


def _rules(defaults_yaml: Path) -> Dict[str, Any]:
    # minimal rules sufficient for aggregation; attempt to extract columns from YAML
    columns = _read_building_columns_from_yaml(defaults_yaml) or [
        "building_id","building_name","object_id","object_name","use_type_set_norm","fitout_condition_mode","delivery_date_earliest","floors_covered_norm","area_sqm_total","listing_count","rent_rate_year_sqm_base_min","rent_rate_year_sqm_base_avg","rent_rate_year_sqm_base_max","rent_vat_norm_mode","opex_year_per_sqm_avg","rent_month_total_gross_avg","sale_price_per_sqm_min","sale_price_per_sqm_avg","sale_price_per_sqm_max","sale_vat_norm_mode","source_files","request_id","quality_flags"
    ]

    return {
        "aggregation": {
            "building": {
                "name": {"compose": "{object_name}{suffix}"},
                "source_files": {"unique_join": " | "},
            }
        },
        "normalization": {
            "use_type": {"canon": ["офис"], "synonyms": {"офис": ["office"]}},
            "fitout_condition": {"canon": ["с отделкой", "под отделку"], "synonyms": {"с отделкой": ["готово к въезду", "есть отделка"], "под отделку": ["готово к отделке", "white box"]}},
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
        "output": {"building_columns": columns},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate AgentQL JSON to building Excel")
    ap.add_argument("json_path", type=Path, help="Path to AgentQL result JSON")
    ap.add_argument("--request-id", dest="request_id", default=None)
    ap.add_argument("--out-name", dest="out_name", default="export.xlsx")
    args = ap.parse_args()

    with args.json_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    defaults_yaml = Path(__file__).resolve().parents[1] / "config" / "defaults.yml"
    rules = _rules(defaults_yaml)

    request_id = args.request_id or (args.json_path.stem.replace(" ", "_") + "_agg")
    rows = group_to_buildings(payload.get("objects") or [], rules, request_id=request_id, source_file=str(args.json_path))

    xlsx = build_xlsx(rows, columns=rules["output"]["building_columns"])
    out_path = build_result_path(request_id, args.out_name, base_dir=Path("data/results"))
    write_bytes(out_path, xlsx)
    print(out_path)


if __name__ == "__main__":
    main()

