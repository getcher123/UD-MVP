from __future__ import annotations

"""
Normalization helpers for listing data: numbers, enums, VAT, floors, and dates,
plus floor parsing/rendering utilities.
"""

import re
from typing import Any, Iterable, Tuple

from services.ids_helper import building_token
from utils.dates import normalize_delivery_date as _normalize_delivery_date


StrOrInt = int | str


# --------- Generic helpers ---------

def to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    s = s.replace("₽", "").replace("$", "").replace("руб", "").replace("р.", "").replace("р", "")
    s = s.replace("м²", "").replace("/м2", "").replace("/м²", "").replace("/м^2", "").replace("/m2", "")
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def map_to_canon(value: Any, rules: dict, section: str) -> str | None:
    if not value:
        return None
    t = str(value).strip().lower()
    sec = rules.get("normalization", {}).get(section, {}) or {}
    for canon in sec.get("canon", []) or []:
        if t == str(canon).lower():
            return str(canon)
    for canon, vals in (sec.get("synonyms", {}) or {}).items():
        for v in vals or []:
            if t == str(v).lower():
                return str(canon)
    return None


def normalize_vat(value: Any, rules: dict) -> str | None:
    if value is None:
        return None
    t = str(value).strip().lower()
    if "включ" in t:
        return "включен"
    not_applied = (rules.get("normalization", {}).get("vat", {}) or {}).get("treat_not_applied", [])
    for token in not_applied or []:
        if token in t:
            return "не применяется"
    if t in {"не применяется", "без ндс", "усн"}:
        return "не применяется"
    return None


def boolish(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    t = str(value).strip().lower()
    if t in {"1", "true", "yes", "y", "да", "+"}:
        return True
    if t in {"0", "false", "no", "n", "нет", "-"}:
        return False
    return None


def normalize_delivery_date(value: Any) -> str | None:
    return _normalize_delivery_date(str(value)) if value is not None else None


# --------- Floors parsing/rendering ---------

def _floor_cfg(cfg: dict) -> dict:
    return cfg.get("floor", cfg)


def _get(cfg: dict, path: list[str], default: Any) -> Any:
    cur: Any = cfg
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _tokenize(value: str, cfg: dict) -> list[str]:
    fc = _floor_cfg(cfg)
    s = value.strip().lower()
    for tok in _get(fc, ["drop_tokens"], ["этаж", "эт", "э."]):
        s = s.replace(tok.lower(), " ")
    seps: list[str] = _get(fc, ["multi", "split_separators"], [",", ";", "/", " и ", "&"])  # type: ignore[assignment]
    for sep in seps:
        s = s.replace(sep, "|")
    parts = [p.strip() for p in s.split("|")]
    return [p for p in parts if p]


def _expand_range(token: str, range_seps: Iterable[str]) -> list[int] | None:
    for d in range_seps:
        m = re.fullmatch(rf"\s*(-?\d+)\s*{re.escape(d)}\s*(-?\d+)\s*", token)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return list(range(min(a, b), max(a, b) + 1))
    return None


def parse_floors(value: Any, cfg: dict) -> list[StrOrInt]:
    fc = _floor_cfg(cfg)
    range_seps = _get(fc, ["multi", "range_separators"], ["-", "–"])  # type: ignore[assignment]
    specials = _get(fc, ["map_special"], {}) or {}
    special_values: dict[str, str] = {}
    for canon, vals in specials.items():
        canon_ru = {"basement": "подвал", "socle": "цоколь", "mezzanine": "мезонин"}.get(canon, canon)
        for v in vals or []:
            special_values[str(v).lower()] = canon_ru

    out: list[StrOrInt] = []

    def handle_token(tok: str) -> None:
        expanded = _expand_range(tok, range_seps)
        if expanded is not None:
            for n in expanded:
                if n == -1 and "-1" in special_values:
                    out.append(special_values["-1"])  # подвал
                else:
                    out.append(n)
            return
        if re.fullmatch(r"-?\d+", tok):
            n = int(tok)
            if n == -1 and "-1" in special_values:
                out.append(special_values["-1"])  # подвал
            else:
                out.append(n)
            return
        if tok in special_values:
            out.append(special_values[tok])
            return

    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        for v in value:
            for t in _tokenize(str(v), cfg):
                handle_token(t)
        return out
    if isinstance(value, int):
        n = int(value)
        return [special_values["-1"]] if n == -1 and "-1" in special_values else [n]

    for t in _tokenize(str(value), cfg):
        handle_token(t)
    return out


def _collapse_consecutive(nums: list[int]) -> list[str]:
    if not nums:
        return []
    nums = sorted(nums)
    ranges: list[tuple[int, int]] = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append((start, prev))
        start = prev = n
    ranges.append((start, prev))
    out: list[str] = []
    for a, b in ranges:
        out.append(str(a) if a == b else f"{a}-@@{b}")
    return out


def render_floors(floors: list[StrOrInt], cfg: dict) -> str:
    fc = _floor_cfg(cfg)
    render = _get(fc, ["multi", "render"], {})
    join_token: str = render.get("join_token", "; ")
    range_dash: str = render.get("range_dash", "–")
    sort_numeric_first: bool = bool(render.get("sort_numeric_first", True))
    uniq: bool = bool(render.get("uniq", True))

    nums: list[int] = []
    texts: list[str] = []
    for f in floors:
        (nums if isinstance(f, int) else texts).append(f if isinstance(f, int) else str(f))

    num_parts = _collapse_consecutive(sorted(set(nums) if uniq else nums))
    if uniq:
        seen: set[str] = set()
        ordered: list[str] = []
        for t in texts:
            if t not in seen:
                ordered.append(t)
                seen.add(t)
        texts = ordered

    pieces = num_parts + texts if sort_numeric_first else texts + num_parts
    return join_token.join(pieces).replace("-@@", range_dash)


# --------- Listing core normalization ---------

def normalize_listing_core(src: dict, parent: dict, rules: dict) -> dict:
    """
    Normalize a single listing record (no IDs/derivations):
    Returns keys: object_name, building_raw, building_token, use_type_norm,
    area_sqm, divisible_from_sqm, floors_norm, market_type, fitout_condition_norm,
    delivery_date_norm, rent_vat_norm, sale_vat_norm, opex_included,
    opex_year_per_sqm, sale_price_per_sqm, rent_rate (if present).
    """
    obj_name = parent.get("object_name") if isinstance(parent, dict) else None
    b_raw = parent.get("building_name") if isinstance(parent, dict) else None
    floor_cfg = rules.get("normalization", {})

    use_norm = map_to_canon(src.get("use_type"), rules, "use_type")
    fit_norm = map_to_canon(src.get("fitout_condition"), rules, "fitout_condition")
    if fit_norm is None and src.get("fitout_condition"):
        # heuristic: any mention of "отдел" w/ positive words → "с отделкой"
        t = str(src.get("fitout_condition")).lower()
        if "отдел" in t and ("с " in t or "есть" in t or "готово к въезду" in t):
            fit_norm = "с отделкой"
        elif "отдел" in t:
            fit_norm = "под отделку"

    floors = parse_floors(src.get("floor"), floor_cfg)
    floors_norm = render_floors(floors, floor_cfg)

    return {
        "object_name": obj_name,
        "building_raw": b_raw,
        "building_token": building_token(b_raw),
        "use_type_norm": use_norm,
        "area_sqm": to_float(src.get("area_sqm")),
        "divisible_from_sqm": to_float(src.get("divisible_from_sqm")),
        "floors_norm": floors_norm,
        "market_type": src.get("market_type"),
        "fitout_condition_norm": fit_norm,
        "delivery_date_norm": normalize_delivery_date(src.get("delivery_date")),
        "rent_vat_norm": normalize_vat(src.get("rent_vat"), rules),
        "sale_vat_norm": normalize_vat(src.get("sale_vat"), rules),
        "opex_included": boolish(src.get("opex_included")),
        "opex_year_per_sqm": to_float(src.get("opex_year_per_sqm")),
        "sale_price_per_sqm": to_float(src.get("sale_price_per_sqm")),
        "rent_rate": to_float(src.get("rent_rate")),
    }


__all__ = [
    "to_float",
    "map_to_canon",
    "normalize_vat",
    "boolish",
    "parse_floors",
    "render_floors",
    "normalize_delivery_date",
    "normalize_listing_core",
]
