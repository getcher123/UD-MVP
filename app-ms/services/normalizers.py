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


_WS_RE = re.compile(r"\s+")


_TOKEN_RE = re.compile(r"[^0-9a-zа-яё%]+")


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = _WS_RE.sub(" ", str(value)).strip()
    return text or None


def _clean_dict_strings(data: dict | None) -> dict:
    if not isinstance(data, dict):
        return {}
    return {key: (_WS_RE.sub(" ", val).strip() if isinstance(val, str) else val) for key, val in data.items()}




def _get_rule_float(rules: dict, path: list[str]) -> float | None:
    cur: object = rules
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None

def _normalize_token(value: Any) -> str | None:
    text = _clean_str(value)
    if not text:
        return None
    return _TOKEN_RE.sub(" ", text.lower()).strip()


# --------- Generic helpers ---------

def to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    s = s.replace("\u2212", "-")  # normalize minus sign
    s = s.replace("\u00A0", "").replace("\u202F", "")  # thin spaces
    s = s.lower()

    for token in ("₽", "$", "руб", "р.", "р", "rub", "usd", "eur"):
        s = s.replace(token, "")
    for token in ("м²", "м2", "/м2", "/м²", "/м^2", "/m2", "sq.m", "sqm"):
        s = s.replace(token, "")

    s = s.replace(" ", "").replace(",", ".")
    s = re.sub(r"[^0-9.+-]", "", s)
    if not s:
        return None

    if s.count('.') > 1:
        parts = s.split('.')
        s = ''.join(parts[:-1]) + '.' + parts[-1]

    sign = ''
    if s[0] in '+-':
        sign = s[0]
        s = s[1:]
    s = sign + s.replace('+', '').replace('-', '')

    try:
        return float(s)
    except ValueError:
        return None


def map_to_canon(value: Any, rules: dict, section: str) -> str | None:
    normalized_value = _normalize_token(value)
    if not normalized_value:
        return None

    sec = rules.get("normalization", {}).get(section, {}) or {}

    def _match(candidate: Any) -> bool:
        normalized_candidate = _normalize_token(candidate)
        if not normalized_candidate:
            return False
        if normalized_value == normalized_candidate:
            return True
        return normalized_candidate in normalized_value

    for canon, vals in (sec.get("synonyms", {}) or {}).items():
        for v in vals or []:
            if _match(v):
                return str(canon)
    for canon in sec.get("canon", []) or []:
        if _match(canon):
            return str(canon)
    return None


def normalize_vat(value: Any, rules: dict) -> str | None:
    if value is None:
        return None
    mapped = map_to_canon(value, rules, "vat")
    if mapped is not None:
        return mapped
    t = _clean_str(value)
    if not t:
        return None
    t_lower = t.lower()
    vat_rules = rules.get("normalization", {}).get("vat", {}) or {}
    for token in (vat_rules.get("treat_not_applied") or []):
        if token.lower() in t_lower:
            return "не применяется"
    if t_lower in {"не применяется", "усн"}:
        return "не применяется"
    return None


def boolish(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    t = _clean_str(value)
    if not t:
        return None
    t = t.lower()
    if t in {"1", "true", "yes", "y", "да", "+"}:
        return True
    if t in {"0", "false", "no", "n", "нет", "-"}:
        return False
    return None


def normalize_delivery_date(value: Any, rules: dict | None = None) -> str | None:
    if value is None:
        return None
    tokens = None
    if rules is not None:
        tokens = rules.get("normalization", {}).get("dates", {}).get("now_tokens")
    return _normalize_delivery_date(str(value), now_tokens=tokens)


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
        match_number = re.search(r"-?\d+", tok)
        if match_number:
            n = int(match_number.group())
            if n == -1 and "-1" in special_values:
                out.append(special_values["-1"])
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



def _derive_market_type(src: dict, fitout: str | None, rules: dict) -> str | None:
    raw = _clean_str(src.get("market_type"))
    if raw:
        return raw
    fallbacks = (rules.get("fallbacks", {}) or {}).get("market_type", {})
    if fitout and isinstance(fallbacks, dict):
        by_fitout = fallbacks.get("by_fitout") or {}
        if fitout in by_fitout:
            return str(by_fitout[fitout])
    return None

def normalize_listing_core(src: dict, parent: dict, rules: dict) -> dict:
    """
    Normalize a single listing record (no IDs/derivations):
    Returns keys: object_name, building_raw, building_token, use_type_norm,
    area_sqm, divisible_from_sqm, floors_norm, market_type, fitout_condition_norm,
    delivery_date_norm, rent_vat_norm, sale_vat_norm, opex_included,
    opex_year_per_sqm, sale_price_per_sqm, rent_rate (if present).
    """
    parent_clean = _clean_dict_strings(parent if isinstance(parent, dict) else {})
    src_clean = _clean_dict_strings(src if isinstance(src, dict) else {})

    obj_name = _clean_str(parent_clean.get("object_name"))
    b_raw = _clean_str(parent_clean.get("building_name"))
    floor_cfg = rules.get("normalization", {})

    use_norm = map_to_canon(src_clean.get("use_type"), rules, "use_type")
    if not use_norm:
        use_norm = (rules.get("fallbacks", {}) or {}).get("use_type_norm", {}).get("default")
    fit_norm = map_to_canon(src_clean.get("fitout_condition"), rules, "fitout_condition")
    if fit_norm is None and _clean_str(src_clean.get("fitout_condition")):
        # heuristic: any mention of "отдел" w/ positive words → "с отделкой"
        t = _clean_str(src_clean.get("fitout_condition")) or ""
        t = t.lower()
        if "отдел" in t and ("с " in t or "есть" in t or "готово к въезду" in t):
            fit_norm = "с отделкой"
        elif "отдел" in t:
            fit_norm = "под отделку"

    floors = parse_floors(src_clean.get("floor"), floor_cfg)
    floors_norm = render_floors(floors, floor_cfg)
    min_base_rate = _get_rule_float(rules, ["quality", "outliers", "rent_rate_year_sqm_base", "min"])
    rent_rate_raw = src_clean.get("rent_rate")
    rent_rate_value = to_float(rent_rate_raw)
    if (rent_rate_value is not None and min_base_rate is not None and rent_rate_value < min_base_rate
            and isinstance(rent_rate_raw, str) and "," in rent_rate_raw):
        cleaned = (_clean_str(rent_rate_raw) or "").replace(",", "")
        alt_rate = to_float(cleaned)
        if alt_rate is not None and alt_rate >= min_base_rate:
            rent_rate_value = alt_rate


    area_val = to_float(src_clean.get("area_sqm"))
    area_int = int(round(area_val)) if area_val is not None else None
    divisible_val = to_float(src_clean.get("divisible_from_sqm"))
    if divisible_val is not None:
        divisible_int = int(round(divisible_val))
    else:
        fallback_cfg = (rules.get("fallbacks", {}) or {}).get("divisible_from_sqm", {})
        if fallback_cfg.get("copy_from") == "area_sqm" and area_int is not None:
            divisible_int = area_int
        else:
            divisible_int = None

    opex_included_value: Optional[str] = None
    opex_included_value: Optional[str] = None
    opex_canon = map_to_canon(src_clean.get("opex_included"), rules, "opex_included")
    if opex_canon in {"включен", "не включен"}:
        opex_included_value = opex_canon
    else:
        bool_val = boolish(src_clean.get("opex_included"))
        if bool_val is True:
            opex_included_value = "включен"
        elif bool_val is False:
            opex_included_value = "не включен"

    rent_vat_norm = normalize_vat(src_clean.get("rent_vat"), rules)
    sale_vat_norm = normalize_vat(src_clean.get("sale_vat"), rules)
    if rent_vat_norm is None and rent_rate_value is not None:
        rv_fallback = (rules.get("fallbacks", {}) or {}).get("rent_vat_norm", {})
        if rv_fallback.get("use_listing_vat", True):
            alt_vat = normalize_vat(src_clean.get("vat"), rules)
            if alt_vat is not None:
                rent_vat_norm = alt_vat
        if rent_vat_norm is None and rv_fallback.get("use_object_rent_vat", True):
            rent_vat_norm = normalize_vat(parent_clean.get("object_rent_vat"), rules)

    return {
        "object_name": obj_name,
        "building_raw": b_raw,
        "building_token": building_token(b_raw),
        "use_type_norm": use_norm,
        "area_sqm": area_int,
        "divisible_from_sqm": divisible_int,
        "floors_norm": floors_norm,
        "market_type": _derive_market_type(src_clean, fit_norm, rules),
        "fitout_condition_norm": fit_norm,
        "delivery_date_norm": normalize_delivery_date(src_clean.get("delivery_date"), rules),
        "rent_vat_norm": rent_vat_norm,
        "sale_vat_norm": sale_vat_norm,
        "opex_included": opex_included_value,
        "opex_year_per_sqm": to_float(src_clean.get("opex_year_per_sqm")),
        "sale_price_per_sqm": to_float(src_clean.get("sale_price_per_sqm")),
        "rent_rate": rent_rate_value,
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
