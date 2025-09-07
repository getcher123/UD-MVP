from __future__ import annotations

"""
Aggregate listings to building-level rows according to rules.

The function `group_to_buildings` expects a list of objects with the shape:

object = {
  "object_name": str,
  "buildings": [
    {"building_name": str|None, "listings": [ {..listing fields..}, ... ]},
  ]
}

It produces a list[dict] with columns strictly from
rules["output"]["building_columns"].

Doctest (minimal happy path):

>>> rules = {
...   "aggregation": {
...     "building": {
...       "name": {"compose": "{object_name}{suffix}"},
...       "source_files": {"unique_join": " | "}
...     }
...   },
...   "output": {"building_columns": [
...       "building_id","building_name","object_id","object_name",
...       "use_type_set_norm","fitout_condition_mode","delivery_date_earliest",
...       "floors_covered_norm","area_sqm_total","listing_count",
...       "rent_rate_year_sqm_base_min","rent_rate_year_sqm_base_avg","rent_rate_year_sqm_base_max",
...       "rent_vat_norm_mode","opex_year_per_sqm_avg","rent_month_total_gross_avg",
...       "sale_price_per_sqm_min","sale_price_per_sqm_avg","sale_price_per_sqm_max",
...       "sale_vat_norm_mode","source_files","request_id","quality_flags"
...   ]},
...   "normalization": {
...       "use_type": {"canon": ["офис"], "synonyms": {"офис": ["office"]}},
...       "fitout_condition": {"canon": ["с отделкой","под отделку"], "synonyms": {"с отделкой": ["готово к въезду"]}},
...       "dates": {"now_tokens": ["сейчас"]},
...   },
...   "derivation": {
...       "rent_rate_year_sqm_base": {"priority": ["direct"], "reconstruct_from_month": {"respect_vat": True, "respect_opex": True, "vat_fallback": 0.2, "round_decimals": 2}},
...       "gross_month_total": {"round_decimals": 2}
...   }
... }
>>> objects = [{
...   "object_name": "Башня",
...   "buildings": [{
...     "building_name": "стр. 1",
...     "listings": [
...       {"use_type": "office", "area_sqm": 100, "rent_rate": 12000, "rent_vat": "не применяется", "floor": "1"},
...       {"use_type": "office", "area_sqm": 50, "rent_rate": 18000, "rent_vat": "не применяется", "floor": "2"},
...     ],
...   }]
... }]
>>> rows = group_to_buildings(objects, rules, request_id="rid1", source_file="/data/x.pdf")
>>> isinstance(rows, list) and all(isinstance(r, dict) for r in rows)
True
"""

import os
from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from services.ids_helper import (
    object_id as make_object_id,
    building_id as make_building_id,
    compose_building_name,
)
from services.derivation import (
    derive_rent_rate_year_sqm_base,
    derive_gross_month_total,
)
from services.normalizers import parse_floors, render_floors
from utils.dates import normalize_delivery_date


def _norm_use_type(val: Any, rules: Dict[str, Any]) -> Optional[str]:
    if not val:
        return None
    t = str(val).strip().lower()
    nuse = rules.get("normalization", {}).get("use_type", {})
    if not isinstance(nuse, dict):
        return t or None
    # direct canon match
    for canon in nuse.get("canon", []) or []:
        if t == str(canon).lower():
            return str(canon)
    # synonyms
    syn = nuse.get("synonyms", {}) or {}
    for canon, vals in syn.items():
        for v in vals or []:
            if t == str(v).lower():
                return str(canon)
    return t or None


def _norm_fitout(val: Any, rules: Dict[str, Any]) -> Optional[str]:
    if not val:
        return None
    t = str(val).strip().lower()
    sec = rules.get("normalization", {}).get("fitout_condition", {}) or {}
    for canon in sec.get("canon", []) or []:
        if t == str(canon).lower():
            return str(canon)
    for canon, vals in (sec.get("synonyms", {}) or {}).items():
        for v in vals or []:
            if t == str(v).lower():
                return str(canon)
    # Reduce to two values heuristic
    if "отдел" in t and ("с " in t or "есть" in t):
        return "с отделкой"
    if "отдел" in t:
        return "под отделку"
    return None


def _norm_vat(val: Any, rules: Dict[str, Any]) -> Optional[str]:
    if val is None:
        return None
    t = str(val).strip().lower()
    if "включ" in t:
        return "включен"
    not_applied = (rules.get("normalization", {}).get("vat", {}) or {}).get("treat_not_applied", [])
    for token in not_applied or []:
        if token in t:
            return "не применяется"
    if t in {"не применяется", "без ндс", "усн"}:
        return "не применяется"
    return None


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    # strip currency and spaces; replace comma with dot
    s = s.replace("₽", "").replace("$", "").replace("руб", "").replace("р.", "").replace("р", "")
    s = s.replace("м²", "").replace("/м2", "").replace("/м²", "").replace("/м^2", "").replace("/m2", "")
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _mode(counter: Counter) -> Optional[Any]:
    if not counter:
        return None
    most = counter.most_common(1)
    return most[0][0] if most else None


def _get(cfg: Dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    cur: Any = cfg
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def group_to_buildings(objects: List[Dict[str, Any]], rules: Dict[str, Any], request_id: str, source_file: str) -> List[Dict[str, Any]]:
    """
    1) Iterate listings of all buildings in all objects
    2) Normalize listing fields (use_type, fitout, dates, VAT/OPEX), compute derivations
    3) Build building key: object_id + building_token (via ids_helper)
    4) Aggregate listing values by key
    5) Return rows with columns exactly as in rules["output"]["building_columns"]
    """
    cols: List[str] = list(_get(rules, ["output", "building_columns"], []) or [])
    join_src = _get(rules, ["aggregation", "building", "source_files", "unique_join"], " | ")

    by_key: Dict[str, Dict[str, Any]] = {}

    src_basename = os.path.basename(source_file) if source_file else ""

    for obj in objects or []:
        object_name = obj.get("object_name") or obj.get("name") or ""
        oid = make_object_id(str(object_name))

        for b in obj.get("buildings") or []:
            raw_bname = b.get("building_name")
            bid = make_building_id(object_name, raw_bname)
            if bid not in by_key:
                # initialize aggregates
                by_key[bid] = {
                    "building_id": bid,
                    "building_name": compose_building_name(object_name, raw_bname, rules),
                    "object_id": oid,
                    "object_name": object_name,
                    "use_type_set_norm": set(),
                    "fitout_condition_counter": Counter(),
                    "rent_vat_counter": Counter(),
                    "sale_vat_counter": Counter(),
                    "area_sqm_total": 0.0,
                    "base_rates": [],
                    "opex_values": [],
                    "gross_month_values": [],
                    "sale_price_values": [],
                    "floors_list": [],
                    "delivery_dates": [],
                    "has_now": False,
                    "source_files_set": set([src_basename]) if src_basename else set(),
                    "listing_count": 0,
                    "quality_flags_set": set(),
                }
            agg = by_key[bid]

            for lst in b.get("listings") or []:
                # Normalize listing fields
                use_norm = _norm_use_type(lst.get("use_type"), rules)
                if use_norm:
                    agg["use_type_set_norm"].add(use_norm)

                fit_norm = _norm_fitout(lst.get("fitout_condition"), rules)
                if fit_norm:
                    agg["fitout_condition_counter"][fit_norm] += 1

                rv = _norm_vat(lst.get("rent_vat"), rules)
                if rv:
                    agg["rent_vat_counter"][rv] += 1
                sv = _norm_vat(lst.get("sale_vat"), rules)
                if sv:
                    agg["sale_vat_counter"][sv] += 1

                # Numbers
                area = _to_float(lst.get("area_sqm")) or 0.0
                agg["area_sqm_total"] += area

                # Floors
                floors = parse_floors(lst.get("floor"), _get(rules, ["normalization", "floor"], {}))
                if floors:
                    agg["floors_list"].extend(floors)

                # Dates
                nd = normalize_delivery_date(lst.get("delivery_date"))
                if nd == "сейчас":
                    agg["has_now"] = True
                elif isinstance(nd, str) and nd:
                    agg["delivery_dates"].append(nd)

                # OPEX
                if lst.get("opex_included"):
                    ov = _to_float(lst.get("opex_year_per_sqm"))
                    if ov is not None:
                        agg["opex_values"].append(ov)

                # Derivations
                base = derive_rent_rate_year_sqm_base(lst, rules)
                if base is not None:
                    agg["base_rates"].append(base)
                gross = derive_gross_month_total(lst, rules)
                if gross is not None:
                    agg["gross_month_values"].append(gross)

                # Sale price
                sp = _to_float(lst.get("sale_price_per_sqm"))
                if sp is not None:
                    agg["sale_price_values"].append(sp)

                # Quality flags
                for q in (lst.get("quality_flags") or []):
                    if q:
                        agg["quality_flags_set"].add(str(q))

                agg["listing_count"] += 1

    # Build final rows per columns
    rows: List[Dict[str, Any]] = []
    floor_cfg = _get(rules, ["normalization", "floor"], {})
    for key, agg in by_key.items():
        # Mode values
        fit_mode = _mode(agg["fitout_condition_counter"]) if agg.get("fitout_condition_counter") else None
        rent_vat_mode = _mode(agg["rent_vat_counter"]) if agg.get("rent_vat_counter") else None
        sale_vat_mode = _mode(agg["sale_vat_counter"]) if agg.get("sale_vat_counter") else None

        # Floors rendered
        floors_rendered = render_floors(agg.get("floors_list") or [], {"floor": floor_cfg}) if agg.get("floors_list") else ""

        # Delivery date earliest
        if agg.get("has_now"):
            earliest = "сейчас"
        else:
            ds = sorted(agg.get("delivery_dates") or [])
            earliest = ds[0] if ds else None

        # Base rates stats
        base_vals = agg.get("base_rates") or []
        sale_vals = agg.get("sale_price_values") or []
        opex_vals = agg.get("opex_values") or []
        gross_vals = agg.get("gross_month_values") or []

        def _min(x: List[float]) -> Optional[float]:
            return min(x) if x else None

        def _max(x: List[float]) -> Optional[float]:
            return max(x) if x else None

        def _avg(x: List[float]) -> Optional[float]:
            return float(mean(x)) if x else None

        row_data: Dict[str, Any] = {
            "building_id": agg["building_id"],
            "building_name": agg["building_name"],
            "object_id": agg["object_id"],
            "object_name": agg["object_name"],
            "use_type_set_norm": ", ".join(sorted(agg["use_type_set_norm"])) if agg.get("use_type_set_norm") else "",
            "fitout_condition_mode": fit_mode,
            "delivery_date_earliest": earliest,
            "floors_covered_norm": floors_rendered,
            "area_sqm_total": round(float(agg.get("area_sqm_total", 0.0)), 2),
            "listing_count": agg.get("listing_count", 0),
            "rent_rate_year_sqm_base_min": _min(base_vals),
            "rent_rate_year_sqm_base_avg": _avg(base_vals),
            "rent_rate_year_sqm_base_max": _max(base_vals),
            "rent_vat_norm_mode": rent_vat_mode,
            "opex_year_per_sqm_avg": _avg(opex_vals),
            "rent_month_total_gross_avg": _avg(gross_vals),
            "sale_price_per_sqm_min": _min(sale_vals),
            "sale_price_per_sqm_avg": _avg(sale_vals),
            "sale_price_per_sqm_max": _max(sale_vals),
            "sale_vat_norm_mode": sale_vat_mode,
            "source_files": join_src.join(sorted(agg.get("source_files_set") or [])),
            "request_id": request_id,
            "quality_flags": ";".join(sorted(agg.get("quality_flags_set") or [])),
        }

        # Emit with exact columns only
        out_row = {col: row_data.get(col) for col in cols}
        rows.append(out_row)

    return rows


__all__ = ["group_to_buildings"]

