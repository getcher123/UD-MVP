from __future__ import annotations

from typing import Any, Dict, List, Sequence

from services.derivation import derive_all
from services.ids_helper import (
    object_id as make_object_id,
    building_token_slug,
    compose_building_name,
    building_id as make_building_id,
    listing_id as make_listing_id,
)
from services.normalizers import normalize_listing_core
from services.excel_export import build_xlsx
from utils.fs import write_bytes


def _round_money(value: Any) -> Any:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return value


def flatten_objects_to_listings(objects: List[Dict[str, Any]], rules: Dict[str, Any], request_id: str, source_file: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for obj in objects or []:
        obj_name = obj.get("object_name")
        for b in (obj.get("buildings") or []):
            b_raw = b.get("building_name")
            for lst in (b.get("listings") or []):
                parent_ctx = {
                    "object_name": obj_name,
                    "building_name": b_raw,
                    "object_rent_vat": obj.get("object_rent_vat"),
                }
                core = normalize_listing_core(lst, parent_ctx, rules)
                deriv = derive_all({**core, **lst}, rules)

                # naming / ids
                btoken_slug = building_token_slug(core.get("building_raw"))
                bname = compose_building_name(core.get("object_name") or "", core.get("building_raw"), rules)
                bid = make_building_id(core.get("object_name") or "", core.get("building_raw"))
                lid = make_listing_id(core, rules, source_file)

                uncertain_set: set[str] = set()
                for value in lst.get("uncertain_parameters") or []:
                    value_str = str(value).strip()
                    if value_str:
                        uncertain_set.add(value_str)
                for value in deriv.get("uncertain_parameters") or []:
                    value_str = str(value).strip()
                    if value_str:
                        uncertain_set.add(value_str)
                uncertain_text = "; ".join(sorted(uncertain_set)) if uncertain_set else None

                row: Dict[str, Any] = {
                    "listing_id": lid,
                    "object_id": make_object_id(core.get("object_name") or ""),
                    "object_name": core.get("object_name"),
                    "building_id": bid,
                    "building_name": bname,
                    "use_type_norm": core.get("use_type_norm"),
                    "area_sqm": core.get("area_sqm"),
                    "divisible_from_sqm": core.get("divisible_from_sqm"),
                    "floors_norm": core.get("floors_norm"),
                    "market_type": core.get("market_type"),
                    "fitout_condition_norm": core.get("fitout_condition_norm"),
                    "delivery_date_norm": core.get("delivery_date_norm"),
                    "rent_rate_year_sqm_base": _round_money(core.get("rent_rate") or deriv.get("rent_rate_year_sqm_base")),
                    "rent_vat_norm": core.get("rent_vat_norm"),
                    "opex_year_per_sqm": _round_money(core.get("opex_year_per_sqm")),
                    "opex_included": core.get("opex_included"),
                    "rent_month_total_gross": _round_money(deriv.get("rent_month_total_gross")),
                    "sale_price_per_sqm": _round_money(core.get("sale_price_per_sqm")),
                    "sale_vat_norm": core.get("sale_vat_norm"),
                    "source_file": source_file.split("/")[-1].split("\\")[-1],
                    "request_id": request_id,
                    "uncertain_parameters": uncertain_text,
                    "recognition_summary": lst.get("recognition_summary"),
                }

                rows.append(row)
    return rows


def export_excel(rows: List[Dict[str, Any]], export_path, columns: Sequence[object]) -> None:
    xlsx = build_xlsx(rows, columns=columns)
    write_bytes(export_path, xlsx)


__all__ = ["flatten_objects_to_listings", "export_excel"]

