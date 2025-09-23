from __future__ import annotations

import re
import calendar
from datetime import date, datetime, timezone
from typing import Iterable, Optional


# --- Existing helpers kept for compatibility ---

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def end_of_quarter(year: int, quarter: int) -> date:
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1..4")
    last_month = quarter * 3
    last_day = calendar.monthrange(year, last_month)[1]
    return date(year, last_month, last_day)


_RE_QY_PATTERNS = [
    re.compile(r"^(?P<q>[1-4])\s*кв\.?[\s/-]*(?P<y>\d{4})$", re.IGNORECASE),  # 1кв-2024, 1 кв. 2024
    re.compile(r"^q\s*(?P<q>[1-4])[\s/-]*(?P<y>\d{4})$", re.IGNORECASE),       # q1-2024, q1 2024
    re.compile(r"^(?P<y>\d{4})[\s/-]*q\s*(?P<q>[1-4])$", re.IGNORECASE),       # 2024q1
    re.compile(r"^(?P<q>[1-4])[\s/-]*(?P<y>\d{4})$"),                           # 1-2024 (ambiguous, treat as q-y)
]


def parse_quarter_year(s: str) -> Optional[date]:
    t = s.strip().lower()
    t = t.replace(" квартал", "кв").replace("квартал", "кв").replace("кв.", "кв")
    for pat in _RE_QY_PATTERNS:
        m = pat.match(t)
        if m:
            q = int(m.group("q"))
            y = int(m.group("y"))
            return end_of_quarter(y, q)
    return None


_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%Y.%m.%d",
    "%Y/%m/%d",
]


def parse_date_loose(s: str) -> Optional[date]:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_quarter(s: str) -> Optional[str]:
    """Parses quarter-year expressions and returns ISO date for end of quarter.

    Backward compatible wrapper that returns an ISO string.
    """
    d = parse_quarter_year(s)
    if d:
        return d.isoformat()
    # Extended support: roman numerals and explicit 'квартал'
    d2 = _parse_quarter_date_extended(s)
    return d2.isoformat() if d2 else None


def to_iso_date(s: str) -> Optional[str]:
    if not s:
        return None
    d = parse_quarter_year(s) or parse_date_loose(s) or _parse_quarter_date_extended(s)
    return d.isoformat() if d else s


# --- New requirements for MS delivery date normalization ---

_LEADING_DATE_PREFIX_PATTERNS = [
    re.compile(r'^(?:>=|<=|=>|=<|>|<|≈|~)\s*', re.IGNORECASE),
    re.compile(r'^(?:с|со|от|до|по|c|from|since|starting|start|начиная\s+с)\s+(?=\S)', re.IGNORECASE),
]


def _strip_delivery_prefixes(text: str) -> str:
    '''Remove auxiliary prefixes (e.g. `с `) before actual date tokens.'''
    if not text:
        return text
    cleaned = text
    while cleaned:
        for pattern in _LEADING_DATE_PREFIX_PATTERNS:
            match = pattern.match(cleaned)
            if match:
                cleaned = cleaned[match.end():]
                break
        else:
            break
    return cleaned.lstrip()


RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

NOW_TOKENS = {"сейчас", "свободно", "готово к въезду", "сегодня"}

RU_MONTHS_NOM = {
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}


def quarter_end(year: int, quarter: int) -> date:
    """
    Возвращает дату последнего дня квартала.
    >>> quarter_end(2025, 1).isoformat()
    '2025-03-31'
    >>> quarter_end(2025, 4).isoformat()
    '2025-12-31'
    """
    return end_of_quarter(year, quarter)


def parse_ddmmyyyy(text: str) -> Optional[date]:
    """
    Поддерживает DD.MM.YYYY и DD/MM/YYYY.
    >>> parse_ddmmyyyy("12.07.2025").isoformat()
    '2025-07-12'
    >>> parse_ddmmyyyy("3/1/2026").isoformat()
    '2026-01-03'
    """
    t = text.strip().lower()
    m = re.match(r"^(?P<d>\d{1,2})[./](?P<m>\d{1,2})[./](?P<y>\d{4})$", t)
    if not m:
        return None
    d = int(m.group("d"))
    mth = int(m.group("m"))
    y = int(m.group("y"))
    try:
        return date(y, mth, d)
    except ValueError:
        return None


def parse_ru_textual_date(text: str) -> Optional[date]:
    """
    Парсит даты вида '12 июля 2025', нечувствительно к регистру и доп. пробелам.
    >>> parse_ru_textual_date("  1  марта 2024 ")
    datetime.date(2024, 3, 1)
    """
    t = re.sub(r"\s+", " ", text.strip().lower())
    m = re.match(r"^(?P<d>\d{1,2})\s+(?P<mon>[а-яё]+)\s+(?P<y>\d{4})$", t)
    if not m:
        return None
    mon_name = m.group("mon")
    mon = _lookup_ru_month(mon_name)
    if not mon:
        return None
    d = int(m.group("d"))
    y = int(m.group("y"))
    try:
        return date(y, mon, d)
    except ValueError:
        return None

def parse_ru_month_year(text: str) -> Optional[date]:
    """Parse expressions like "февраль 2025" -> first day of month."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    m = re.match(r"^(?P<mon>[а-яё]+)\s+(?P<y>\d{4})$", t)
    if not m:
        return None
    mon = _lookup_ru_month(m.group("mon"))
    if not mon:
        return None
    year = int(m.group("y"))
    return date(year, mon, 1)




_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}




def _lookup_ru_month(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    token = token.lower()
    if token in RU_MONTHS:
        return RU_MONTHS[token]
    if token in RU_MONTHS_NOM:
        return RU_MONTHS_NOM[token]
    return None

def _parse_quarter_date_extended(text: str) -> Optional[date]:
    """Extended quarter parser supporting roman numerals and 'квартал' tokens."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    # Q1 2025, q2-2026
    m = re.match(r"^q\s*(?P<q>[1-4])\s*[- ]\s*(?P<y>\d{4})$", t)
    if m:
        return end_of_quarter(int(m.group("y")), int(m.group("q")))
    # 1 кв 2026 or 1кв 2026
    m = re.match(r"^(?P<q>[1-4])\s*кв\.?\s*(?P<y>\d{4})$", t)
    if m:
        return end_of_quarter(int(m.group("y")), int(m.group("q")))
    m = re.match(r"^(?P<q>[1-4])\s*квартал\s*(?P<y>\d{4})$", t)
    if m:
        return end_of_quarter(int(m.group("y")), int(m.group("q")))
    # Roman numerals: I квартал 2026, III квартал 2026
    m = re.match(r"^(?P<r>i{1,3}|iv)\s*квартал\s*(?P<y>\d{4})$", t)
    if m:
        q = _ROMAN.get(m.group("r"))
        if q:
            return end_of_quarter(int(m.group("y")), q)
    return None


def parse_quarter(text: str) -> Optional[str]:  # type: ignore[override]
    # Overridden above for compatibility; keep alias for clarity
    return to_quarter_end_iso(text)


def to_quarter_end_iso(text: str) -> Optional[str]:
    d = parse_quarter_year(text) or _parse_quarter_date_extended(text)
    return d.isoformat() if d else None


def normalize_delivery_date(text: Optional[str], now_tokens: Optional[Iterable[str]] = None) -> Optional[str]:
    """
    Normalize delivery date strings to ISO format or the canonical token 'сейчас'.
    """
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None

    t = _strip_delivery_prefixes(t)
    if not t:
        return None

    tokens = {token.lower().strip() for token in NOW_TOKENS}
    if now_tokens:
        for token in now_tokens:
            if token is not None:
                tokens.add(str(token).lower().strip())

    low = t.lower()
    if low in tokens:
        return "сейчас"

    # explicit numeric formats
    d = parse_ddmmyyyy(low)
    if d:
        return d.isoformat()

    # textual russian date
    d = parse_ru_textual_date(low)
    if d:
        return d.isoformat()

    # month + year (e.g. "февраль 2025")
    d = parse_ru_month_year(low)
    if d:
        return d.isoformat()

    # quarters
    d = parse_quarter_year(low) or _parse_quarter_date_extended(low)
    if d:
        return d.isoformat()

    return None


__all__ = [
    # legacy helpers
    "now_iso",
    "end_of_quarter",
    "parse_quarter_year",
    "parse_quarter",
    "parse_date_loose",
    "to_iso_date",
    # new API
    "RU_MONTHS",
    "NOW_TOKENS",
    "quarter_end",
    "parse_ddmmyyyy",
    "parse_ru_textual_date",
    "normalize_delivery_date",
    "to_quarter_end_iso",
]
