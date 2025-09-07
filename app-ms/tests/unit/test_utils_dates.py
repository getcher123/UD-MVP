from __future__ import annotations

import sys
from pathlib import Path

# Надёжно находим корень проекта, чтобы импортировать 'utils'
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from utils import dates as dt  # type: ignore


def test_now_tokens_case_insensitive():
    assert dt.normalize_delivery_date("свободно") == "сейчас"
    assert dt.normalize_delivery_date("ГОТОВО К ВЪЕЗДУ") == "сейчас"
    assert dt.normalize_delivery_date("  СеЙчАс  ") == "сейчас"


def test_parse_ddmmyyyy_variants():
    assert dt.normalize_delivery_date("12.07.2025") == "2025-07-12"
    assert dt.normalize_delivery_date("3/1/2026") == "2026-01-03"  # dd/mm/yyyy


def test_parse_ru_textual_date():
    assert dt.normalize_delivery_date("  1  марта 2024 ") == "2024-03-01"
    assert dt.normalize_delivery_date("12 июля 2025") == "2025-07-12"


def test_parse_quarter_variants():
    assert dt.normalize_delivery_date("Q4 2025") == "2025-12-31"
    assert dt.normalize_delivery_date("4кв2026") == "2026-12-31"      # без пробела
    assert dt.normalize_delivery_date("2 кв 2028") == "2028-06-30"
    assert dt.normalize_delivery_date("iv квартал 2027") == "2027-12-31"  # римские


def test_invalid_dates():
    assert dt.normalize_delivery_date(None) is None
    assert dt.normalize_delivery_date("") is None
    assert dt.normalize_delivery_date("32/13/2025") is None
    assert dt.normalize_delivery_date("какая-то ерунда") is None
