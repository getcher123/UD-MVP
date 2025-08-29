from __future__ import annotations

from io import BytesIO
from typing import Iterable, Mapping

from openpyxl import Workbook


def build_xlsx(rows: Iterable[Mapping]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Result"

    rows = list(rows)
    if not rows:
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # Headers
    headers = list(rows[0].keys())
    ws.append(headers)

    # Data
    for r in rows:
        ws.append([r.get(h) for h in headers])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

