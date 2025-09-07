from __future__ import annotations

"""
Floor parsing and rendering helpers.

The functions operate on a small config dict fragment, typically taken from
`normalization.floor` section of defaults.yml. They are side‑effect free and
contain doctests for core scenarios.

Examples (doctest):

>>> cfg = {
...     "floor": {
...         "drop_tokens": ["этаж", "эт", "э."],
...         "map_special": {
...             "basement": ["подвал", "-1"],
...             "socle": ["цоколь"],
...             "mezzanine": ["мезонин"],
...         },
...         "multi": {
...             "enabled": True,
...             "split_separators": [",", ";", "/", " и ", "&"],
...             "range_separators": ["-", "–"],
...             "render": {"join_token": "; ", "range_dash": "–", "sort_numeric_first": True, "uniq": True},
...         },
...     }
... }
>>> render_floors(parse_floors("1 и 2", cfg), cfg)
'1–2'
>>> render_floors(parse_floors("1,3;5", cfg), cfg)
'1; 3; 5'
>>> render_floors(parse_floors("цоколь/1-2", cfg), cfg)
'1–2; цоколь'
"""

import re
from typing import Any, Iterable


StrOrInt = int | str


def _floor_cfg(cfg: dict) -> dict:
    """Accept either the root normalization config or the `floor` slice."""
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
    # drop tokens like "этаж", "эт", "э."
    for tok in _get(fc, ["drop_tokens"], ["этаж", "эт", "э."]):
        s = s.replace(tok.lower(), " ")

    # split by multi separators
    seps: list[str] = _get(fc, ["multi", "split_separators"], [",", ";", "/", " и ", "&"])  # type: ignore[assignment]
    for sep in seps:
        s = s.replace(sep, "|")
    parts = [p.strip() for p in s.split("|")]
    return [p for p in parts if p]


def _expand_range(token: str, range_seps: Iterable[str]) -> list[int] | None:
    for d in range_seps:
        # Strictly two integers separated by dash char
        m = re.fullmatch(rf"\s*(-?\d+)\s*{re.escape(d)}\s*(-?\d+)\s*", token)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                return list(range(a, b + 1))
            else:
                return list(range(b, a + 1))
    return None


def parse_floors(value: Any, cfg: dict) -> list[StrOrInt]:
    """
    Parse a value into a list of floors represented by ints or special strings
    ("цоколь", "мезонин", "подвал"). Supports multiple tokens and ranges.
    Removes tokens like "этаж"/"эт"/"э.".
    """
    fc = _floor_cfg(cfg)
    range_seps = _get(fc, ["multi", "range_separators"], ["-", "–"])  # type: ignore[assignment]
    specials = _get(fc, ["map_special"], {}) or {}
    special_values: dict[str, str] = {}
    # Flatten mapping to canonical russian strings
    for canon, vals in specials.items():
        canon_ru = {
            "basement": "подвал",
            "socle": "цоколь",
            "mezzanine": "мезонин",
        }.get(canon, canon)
        for v in vals or []:
            special_values[str(v).lower()] = canon_ru

    out: list[StrOrInt] = []

    def handle_token(tok: str) -> None:
        # Ranges first
        expanded = _expand_range(tok, range_seps)
        if expanded is not None:
            for n in expanded:
                if n == -1 and "-1" in special_values:
                    out.append(special_values["-1"])  # "подвал"
                else:
                    out.append(n)
            return

        # Pure number
        if re.fullmatch(r"-?\d+", tok):
            n = int(tok)
            if n == -1 and "-1" in special_values:
                out.append(special_values["-1"])  # "подвал"
            else:
                out.append(n)
            return

        # Special textual floors
        if tok in special_values:
            out.append(special_values[tok])
            return

        # Otherwise ignore unrecognized textual tokens

    # Dispatch based on type
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        for v in value:
            for t in _tokenize(str(v), cfg):
                handle_token(t)
        return out
    if isinstance(value, (int,)):
        n = int(value)
        if n == -1 and "-1" in special_values:
            return [special_values["-1"]]
        return [n]

    # Fallback: parse as string
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
        if a == b:
            out.append(str(a))
        else:
            out.append(f"{a}-@@{b}")  # temporary token; dash replaced later
    return out


def render_floors(floors: list[StrOrInt], cfg: dict) -> str:
    """
    Sort numeric floors first, collapse consecutive integers into ranges, ensure
    uniqueness, then join pieces using join_token. Special text floors are kept.
    """
    fc = _floor_cfg(cfg)
    render = _get(fc, ["multi", "render"], {})
    join_token: str = render.get("join_token", "; ")
    range_dash: str = render.get("range_dash", "–")
    sort_numeric_first: bool = bool(render.get("sort_numeric_first", True))
    uniq: bool = bool(render.get("uniq", True))

    nums: list[int] = []
    texts: list[str] = []
    for f in floors:
        if isinstance(f, int):
            nums.append(f)
        else:
            texts.append(str(f))

    # Prepare numeric part
    num_parts = _collapse_consecutive(sorted(set(nums) if uniq else nums))
    # Prepare textual part (preserve first occurrence order when uniq)
    if uniq:
        seen: set[str] = set()
        tparts: list[str] = []
        for t in texts:
            if t not in seen:
                tparts.append(t)
                seen.add(t)
        texts = tparts

    pieces = num_parts + texts if sort_numeric_first else texts + num_parts
    result = join_token.join(pieces).replace("-@@", range_dash)
    return result


__all__ = ["parse_floors", "render_floors"]

