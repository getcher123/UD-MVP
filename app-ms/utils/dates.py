from __future__ import annotations

import re
from datetime import date, datetime, timezone
import calendar
from typing import Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def end_of_quarter(year: int, quarter: int) -> date:
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1..4")
    # End months: Mar, Jun, Sep, Dec
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
    """Parses quarter-year expressions and returns ISO date for end of quarter."""
    d = parse_quarter_year(s)
    return d.isoformat() if d else None


def to_iso_date(s: str) -> Optional[str]:
    if not s:
        return None
    d = parse_quarter_year(s) or parse_date_loose(s)
    return d.isoformat() if d else s


__all__ = [
    "now_iso",
    "end_of_quarter",
    "parse_quarter_year",
    "parse_quarter",
    "parse_date_loose",
    "to_iso_date",
]
