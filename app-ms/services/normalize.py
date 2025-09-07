from __future__ import annotations

from typing import Any, Dict, List, Tuple


def normalize(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize AgentQL result rows (stub)."""
    return rows


def normalize_agentql_payload(payload: Dict[str, Any], rules: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Map AgentQL payload to domain objects structure expected by aggregators.

    Accepts either:
    - { "objects": [...] }
    - { "data": { "objects": [...] }, ... }

    Returns (objects, pending_questions). For MVP, pending_questions = [].

    >>> payload = {"data": {"objects": [{"object_name": "X", "buildings": []}]}}
    >>> objs, qs = normalize_agentql_payload(payload, {})
    >>> isinstance(objs, list) and objs[0].get("object_name") == "X" and qs == []
    True
    """
    root = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    objects = root.get("objects") if isinstance(root, dict) else None
    if not isinstance(objects, list):
        return [], []

    # Ensure shape consistency: buildings/listings are lists
    out: List[Dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        blds = obj.get("buildings")
        if not isinstance(blds, list):
            blds = []
        b_out: List[Dict[str, Any]] = []
        for b in blds:
            if not isinstance(b, dict):
                continue
            lsts = b.get("listings")
            if not isinstance(lsts, list):
                lsts = []
            b2 = dict(b)
            b2["listings"] = lsts
            b_out.append(b2)
        o2 = dict(obj)
        o2["buildings"] = b_out
        out.append(o2)

    return out, []


__all__ = ["normalize", "normalize_agentql_payload"]

