from __future__ import annotations

"""
Derivation helpers for listing-level metrics.

Implements:
- derive_rent_rate_year_sqm_base(listing, rules)
- derive_gross_month_total(listing, rules)
- derive_all(listing_norm, rules)

Rules schema (subset) expected from YAML defaults (see app-ms/config/defaults.yml):
- derivation.rent_rate_year_sqm_base.priority: ["direct", "reconstruct_from_month"]
- derivation.rent_rate_year_sqm_base.reconstruct_from_month: respect_vat, respect_opex, vat_fallback, round_decimals
- derivation.gross_month_total.round_decimals
- quality.outliers.rent_rate_year_sqm_base.min/max
"""

from typing import Any, Dict, Optional


def _r(d: Dict[str, Any], path: list[str], default: Any = None) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _round_opt(x: Optional[float], ndigits: Optional[int]) -> Optional[float]:
    if x is None or ndigits is None:
        return x
    try:
        return round(x, int(ndigits))
    except Exception:
        return x


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _vat_rate(listing: Dict[str, Any], rules: Dict[str, Any]) -> float:
    fallback = float(_r(rules, ["derivation", "rent_rate_year_sqm_base", "reconstruct_from_month", "vat_fallback"], 0.20))
    # No explicit rate in listing; use fallback
    return fallback


def _vat_included(listing: Dict[str, Any]) -> bool:
    v = str(listing.get("rent_vat") or "").strip().lower()
    return v == "включен" or v == "включён"


def derive_rent_rate_year_sqm_base(listing: Dict[str, Any], rules: Dict[str, Any]) -> Optional[float]:
    """
    Derive base annual rent rate per sqm (excluding VAT and OPEX) using rules.

    Strategy:
    1) direct: if listing contains numeric 'rent_rate' (per year per sqm), adjust for VAT if included.
    2) reconstruct_from_month: if listing has 'rent_cost_month_per_room' and 'area_sqm', compute
       (monthly_total*12/area). If VAT included, divide by (1+vat). If opex_included is True,
       subtract 'opex_year_per_sqm'.
    Applies rounding and quality outlier filtering per rules. Returns None if cannot derive or filtered out.
    """
    priority = _r(rules, ["derivation", "rent_rate_year_sqm_base", "priority"], ["direct", "reconstruct_from_month"]) or []
    respect_vat = bool(_r(rules, ["derivation", "rent_rate_year_sqm_base", "reconstruct_from_month", "respect_vat"], True))
    respect_opex = bool(_r(rules, ["derivation", "rent_rate_year_sqm_base", "reconstruct_from_month", "respect_opex"], True))
    ndigits = _r(rules, ["derivation", "rent_rate_year_sqm_base", "reconstruct_from_month", "round_decimals"], 2)

    vat_rate = _vat_rate(listing, rules)

    def step_direct() -> Optional[float]:
        rr = _as_float(listing.get("rent_rate"))
        if rr is None:
            return None
        # Treat provided value as possibly VAT-included; normalize to base if so
        if respect_vat and _vat_included(listing):
            rr = rr / (1.0 + vat_rate)
        return rr

    def step_reconstruct() -> Optional[float]:
        monthly_total = _as_float(listing.get("rent_cost_month_per_room"))
        area = _as_float(listing.get("area_sqm"))
        if monthly_total is None or area in (None, 0):
            return None
        rate = (monthly_total * 12.0) / float(area)
        if respect_vat and _vat_included(listing):
            rate = rate / (1.0 + vat_rate)
        if respect_opex and bool(listing.get("opex_included")) and _as_float(listing.get("opex_year_per_sqm")) not in (None, 0):
            rate = rate - float(listing["opex_year_per_sqm"])  # per sqm-year
        return rate

    # run-through in order
    value: Optional[float] = None
    for key in priority:
        if key == "direct":
            value = step_direct()
        elif key == "reconstruct_from_month":
            value = step_reconstruct()
        if value is not None:
            break

    # rounding
    value = _round_opt(value, ndigits)

    # quality filtering
    if value is not None:
        qmin = _as_float(_r(rules, ["quality", "outliers", "rent_rate_year_sqm_base", "min"], None))
        qmax = _as_float(_r(rules, ["quality", "outliers", "rent_rate_year_sqm_base", "max"], None))
        if qmin is not None and value < qmin:
            return None
        if qmax is not None and value > qmax:
            return None

    return value


def derive_gross_month_total(listing: Dict[str, Any], rules: Dict[str, Any]) -> Optional[float]:
    """
    Derive gross monthly total for the room.

    If 'rent_cost_month_per_room' exists, return it.
    Otherwise, reconstruct from base per-sqm-year rate and area, then re-apply VAT and OPEX
    when applicable. Returns rounded value per rules.
    """
    # direct
    direct = _as_float(listing.get("rent_cost_month_per_room"))
    ndigits = _r(rules, ["derivation", "gross_month_total", "round_decimals"], 2)
    if direct is not None:
        return _round_opt(direct, ndigits)

    # reconstruct from base
    base = derive_rent_rate_year_sqm_base(listing, rules)
    area = _as_float(listing.get("area_sqm"))
    if base is None or area in (None, 0):
        return None
    monthly = (base * float(area)) / 12.0

    # add VAT back if included
    if _vat_included(listing):
        monthly *= (1.0 + _vat_rate(listing, rules))

    # add OPEX if included
    if bool(listing.get("opex_included")) and _as_float(listing.get("opex_year_per_sqm")) not in (None, 0):
        monthly += float(listing["opex_year_per_sqm"]) * float(area) / 12.0

    return _round_opt(monthly, ndigits)


def derive_all(listing: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute all derived metrics and uncertainty hints from a normalized listing dict.
    Returns keys: rent_rate_year_sqm_base, gross_month_total, uncertain_parameters (list).
    """
    out: Dict[str, Any] = {}
    uncertain_fields: set[str] = set()

    base = derive_rent_rate_year_sqm_base(listing, rules)
    if base is not None:
        out["rent_rate_year_sqm_base"] = base

    monthly = derive_gross_month_total(listing, rules)
    if monthly is not None:
        out["rent_month_total_gross"] = monthly

    # Quality flags
    area = _as_float(listing.get("area_sqm"))
    if area is not None and area <= 0:
        uncertain_fields.add("area_sqm")
    qmin = _as_float(_r(rules, ["quality", "outliers", "rent_rate_year_sqm_base", "min"], None))
    qmax = _as_float(_r(rules, ["quality", "outliers", "rent_rate_year_sqm_base", "max"], None))
    if base is not None:
        if qmin is not None and base < qmin:
            uncertain_fields.add("rent_rate_year_sqm_base")
        if qmax is not None and base > qmax:
            uncertain_fields.add("rent_rate_year_sqm_base")

    out["uncertain_parameters"] = sorted(uncertain_fields)

    return out


__all__ = [
    "derive_rent_rate_year_sqm_base",
    "derive_gross_month_total",
    "derive_all",
]
