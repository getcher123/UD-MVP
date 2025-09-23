from __future__ import annotations

"""
Helpers for generating object/building identifiers and names.

Doctest examples:

>>> rules = {"aggregation": {"building": {"name": {"compose": "{object_name}{suffix}"}}}}
>>> obj = "Башня на Набережной"
>>> raw = "стр. 1"
>>> building_id(obj, raw)
'bashnya-na-naberezhnoy__str-1'
>>> compose_building_name(obj, raw, rules)
'Башня на Набережной, стр. 1'

>>> building_id("Комета", None)
'kometa'
>>> compose_building_name("Комета", None, rules)
'Комета'
"""

import re
from typing import Optional


_RU_TRANS = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _transliterate_ru(s: str) -> str:
    out = []
    for ch in s:
        low = ch.lower()
        if low in _RU_TRANS:
            t = _RU_TRANS[low]
            out.append(t)
        else:
            out.append(ch)
    return "".join(out)


def slug(s: str) -> str:
    """
    Build a URL/ID-friendly slug:
    - transliterate Russian letters to latin
    - lowercase
    - keep ascii letters, digits, hyphens; replace other runs with '-'
    - collapse consecutive hyphens, strip leading/trailing hyphens
    """
    t = _transliterate_ru(s).lower()
    # replace non-alnum with hyphen
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return t


_RE_STR = re.compile(r"\bстр\.?\s*(?P<n>\d+)\b", re.IGNORECASE)
_RE_KORPUS = re.compile(r"\bкорпус\s*(?P<n>\d+)\b", re.IGNORECASE)
_RE_LITERA = re.compile(r"\bлитер(?:а|ы)?\s*(?P<l>[A-Za-zА-Яа-я])\b", re.IGNORECASE)
_RE_BLOK = re.compile(r"\bблок\s*(?P<b>[A-Za-zА-Яа-я])\b", re.IGNORECASE)


def building_token(raw_building_name: str | None) -> Optional[str]:
    """
    Extract building token from a free-form building name.
    Supported tokens: "стр. N", "литера X", "корпус N", "блок X".
    If nothing recognized: return cleaned text or None if empty.
    """
    if not raw_building_name:
        return None
    s = str(raw_building_name).strip()
    if not s:
        return None

    m = _RE_STR.search(s)
    if m:
        return f"стр. {int(m.group('n'))}"
    m = _RE_KORPUS.search(s)
    if m:
        return f"корпус {int(m.group('n'))}"
    m = _RE_LITERA.search(s)
    if m:
        return f"литера {m.group('l').upper()}"
    m = _RE_BLOK.search(s)
    if m:
        return f"блок {m.group('b').upper()}"

    # Fallback: if string is not empty and doesn't look like object name, return as-is
    return s or None


def building_token_slug(raw_building_name: str | None) -> str:
    tok = building_token(raw_building_name)
    return slug(tok) if tok else ""


def object_id(object_name: str) -> str:
    return slug(object_name)


def building_id(object_name: str, raw_building_name: str | None) -> str:
    oid = object_id(object_name)
    bslug = building_token_slug(raw_building_name)
    return f"{oid}__{bslug}" if bslug else oid


def compose_building_name(object_name: str, raw_building_name: str | None, rules: dict) -> str:
    """
    Compose building display name according to template
    `aggregation.building.name.compose` where suffix is `, {token}` if token exists.
    """
    raw_clean = str(raw_building_name).strip() if raw_building_name else ""
    obj_clean = (object_name or "").strip()
    if raw_clean and obj_clean and obj_clean.lower() in raw_clean.lower():
        return raw_clean

    token = building_token(raw_building_name)
    suffix = ""
    if token:
        if not (obj_clean and token.lower() in obj_clean.lower()):
            suffix = f", {token}"
    template = (
        rules.get("aggregation", {})
        .get("building", {})
        .get("name", {})
        .get("compose", "{object_name}{suffix}")
        if isinstance(rules, dict)
        else "{object_name}{suffix}"
    )
    base_name = obj_clean or object_name
    return template.format(object_name=base_name, suffix=suffix) if template else (raw_clean or base_name)


__all__ = [
    "slug",
    "building_token",
    "building_token_slug",
    "object_id",
    "building_id",
    "compose_building_name",
]

# Listing identifier generation per rules v3
from hashlib import sha256
from typing import Any, Dict


def listing_id(core: Dict[str, Any], rules: Dict[str, Any], source_file: str) -> str:
    """
    Compose stable listing_id from normalized parts and a short hash of source file basename.

    Uses rules.identifier.listing_id: compose_parts, hash_len, join_token.
    Recognized part keys: object_id, building_token_slug, use_type_norm_slug, floors_norm_slug, area_1dp.
    """
    ident = rules.get("identifier", {}).get("listing_id", {}) or {}
    parts_keys = ident.get("compose_parts", []) or []
    join_token = ident.get("join_token", "__")
    hash_len = int(ident.get("hash_len", 8))

    values: Dict[str, Any] = {}
    values["object_id"] = object_id(core.get("object_name") or "")
    values["building_token_slug"] = building_token_slug(core.get("building_raw"))
    values["use_type_norm_slug"] = slug(core.get("use_type_norm") or "")
    values["floors_norm_slug"] = slug(core.get("floors_norm") or "")
    area = core.get("area_sqm")
    values["area_1dp"] = f"{area:.1f}" if isinstance(area, (int, float)) else ""

    seq = [str(values.get(k, "")) for k in parts_keys]
    base = join_token.join(seq)

    base_name = (source_file or "").split("/")[-1].split("\\")[-1]
    digest = sha256(base_name.encode("utf-8")).hexdigest()[:hash_len]
    return f"{base}{join_token}{digest}" if base else digest

