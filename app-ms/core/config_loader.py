from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _read_mapping_from_yaml(path: Path, key: str) -> Dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    lines = text.splitlines()
    inside = False
    base_indent = None
    stack: list[tuple[int, Dict[str, Any]]] = []
    mapping: Dict[str, Any] = {}

    for ln in lines:
        stripped = ln.strip()
        if not inside:
            if stripped.startswith(f"{key}:"):
                inside = True
                base_indent = len(ln) - len(stripped)
                stack = [(base_indent, mapping)]
            continue

        if stripped == "" or stripped.startswith('#'):
            continue

        indent = len(ln) - len(stripped)
        if indent <= (base_indent or 0):
            break

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            stack = [(base_indent or 0, mapping)]
        parent = stack[-1][1]

        if ':' not in stripped:
            continue
        key_part, value_part = stripped.split(':', 1)
        key_part = key_part.strip()
        value_part = value_part.strip()
        if value_part == "":
            parent[key_part] = {}
            stack.append((indent, parent[key_part]))
        else:
            val_lower = value_part.lower()
            if val_lower in {"true", "false"}:
                value = val_lower == "true"
            else:
                if value_part.startswith("[") and value_part.endswith("]"):
                    try:
                        value = json.loads(value_part)
                    except json.JSONDecodeError:
                        value = value_part
                else:
                    if len(value_part) >= 2 and value_part[0] == value_part[-1] and value_part[0] in ('"', '\''):
                        value_part = value_part[1:-1]
                    value = value_part
            parent[key_part] = value

    return mapping or None


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
        "uncertain_parameters",
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
        "recognition_summary",
        "uncertain_parameters",
    ]

    now_tokens = _read_sequence_from_yaml(p, "now_tokens") or []

    normalization: Dict[str, Any] = {
        "use_type": {
            "canon": ["офис", "ритейл", "псн", "склад"],
            "synonyms": {
                "офис": ["office", "open space", "офис open space", "open-space", "смешанная", "смешанная планировка", "кабинетная", "кабинетная планировка"],
                "ритейл": ["retail", "street-retail", "street retail", "стрит-ритейл"],
                "псн": ["psn", "псн", "помещение свободного назначения", "свободного назначения", "нежилое помещение свободного назначения"],
                "склад": ["storage", "warehouse", "складское помещение"],
            },
        },
        "fitout_condition": {
            "canon": ["с отделкой", "под отделку"],
            "synonyms": {
                "с отделкой": [
                    "с готовым ремонтом",
                    "готово к въезду",
                    "с мебелью",
                    "есть отделка",
                    "выполнен ремонт",
                    "полностью готово к",
                    "гипсовые перегородки",
                    "за выездом арендатора",
                ],
                "под отделку": ["white box", "готово к отделке"],
            },
        },
        "vat": {
            "canon": ["включен", "не включен", "не применяется"],
            "synonyms": {
                "включен": ["включая НДС", "с НДС", "НДС включен", "ставка с НДС", "вкл. НДС", "с учетом НДС"],
                "не применяется": ["УСН", "УСН, без НДС", "освобождено", "не облагается НДС", "НДС 5%", "без НДС (УСН)", "УСН без НДС"],
                "не включен": ["без НДС", "без НДС.", "без учета НДС", "НДС не включен", "не включая НДС", "начисляется НДС"],
            },
        },
        "opex_included": {
            "canon": ["включен", "не включен"],
            "synonyms": {
                "включен": ["включая эксплуатационные услуги", "opex включен"],
                "не включен": ["opex не включен"],
            },
        },
        "floor": {
            "drop_tokens": ["этаж", "эт", "э."],
            "map_special": {
                "basement": ["подвал", "-1"],
                "socle": ["цоколь"],
                "mezzanine": ["мезонин"],
            },
            "multi": {
                "enabled": True,
                "split_separators": [",", ";", "/", " и ", "&"],
                "range_separators": ["-", "–"],
                "render": {
                    "join_token": "; ",
                    "range_dash": "–",
                    "sort_numeric_first": True,
                    "uniq": True,
                },
            },
        },
    }

    if now_tokens:
        normalization["dates"] = {"now_tokens": now_tokens}

    fallbacks = _read_mapping_from_yaml(p, "fallbacks") or {
        "rent_vat_norm": {"use_listing_vat": True, "use_object_rent_vat": True}
    }

    pipeline_cfg = _read_mapping_from_yaml(p, "pipeline") or {}

    return {
        "aggregation": {
            "building": {
                "name": {"compose": "{object_name}{suffix}"},
                "source_files": {"unique_join": " | "},
            }
        },
        "normalization": normalization,
        "fallbacks": fallbacks,
        "derivation": {
            "rent_rate_year_sqm_base": {
                "priority": ["direct", "reconstruct_from_month"],
                "reconstruct_from_month": {"respect_vat": True, "respect_opex": True, "vat_fallback": 0.2, "round_decimals": 2},
            },
            "gross_month_total": {"round_decimals": 2},
        },
        "output": {"building_columns": building_columns, "listing_columns": listing_columns},
        "quality": {"outliers": {"rent_rate_year_sqm_base": {"min": 1000, "max": 200000}}},
        "pipeline": pipeline_cfg,
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
