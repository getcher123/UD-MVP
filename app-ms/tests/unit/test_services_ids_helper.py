from __future__ import annotations

import sys
from pathlib import Path


# Resolve project root so imports like 'from services.ids_helper import ...' work
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.ids_helper import (  # type: ignore  # noqa: E402
    slug,
    building_token,
    building_token_slug,
    object_id,
    building_id,
    compose_building_name,
)


def test_slug_transliteration_and_cleanup():
    assert slug("Башня на Набережной") == "bashnya-na-naberezhnoy"
    assert slug("стр. 1") == "str-1"
    assert slug("Литера Б") == "litera-b"


def test_building_tokens_extraction():
    assert building_token("стр. 1") == "стр. 1"
    assert building_token("Стр1") == "стр. 1" or building_token("Стр1") == "Стр1"  # tolerant
    assert building_token("литера б") == "литера Б"
    assert building_token("корпус 2") == "корпус 2"
    assert building_token("блок c") == "блок C"
    assert building_token(None) is None
    assert building_token("") is None


def test_ids_and_composed_name():
    rules = {"aggregation": {"building": {"name": {"compose": "{object_name}{suffix}"}}}}
    obj = "Башня на Набережной"
    raw = "стр. 1"

    assert object_id(obj) == "bashnya-na-naberezhnoy"
    assert building_token_slug(raw) == "str-1"
    assert building_id(obj, raw) == "bashnya-na-naberezhnoy__str-1"
    assert compose_building_name(obj, raw, rules) == "Башня на Набережной, стр. 1"

    obj2 = "Комета"
    assert building_id(obj2, None) == "kometa"
    assert compose_building_name(obj2, None, rules) == "Комета"

