from __future__ import annotations

from io import BytesIO
from typing import Iterable, Mapping, Sequence

from openpyxl import Workbook


def build_xlsx(rows: list[dict], columns: Sequence[str] | None = None) -> bytes:
    """
    Build an Excel workbook from rows using the exact column order provided.

    - rows: list of dictionaries (values may be None/int/float/str)
    - columns: ordered list of column names; if None, derived from first row's keys
    - Applies:
      - header row freeze (A2)
      - auto filter across the used range
      - simple number formats: int -> "0", float -> "0.00"
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Result"

    rows = list(rows or [])
    if not rows:
        headers = list(columns) if columns is not None else []
        if headers:
            ws.append(headers)
            # Freeze panes and add autofilter even if no data rows
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    headers = list(columns) if columns is not None else list(rows[0].keys())
    ws.append(headers)

    for r in rows:
        row_vals = []
        for h in headers:
            v = r.get(h)
            row_vals.append(v)
        ws.append(row_vals)

    # Apply simple number formats (no currency symbols)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            val = cell.value
            if isinstance(val, int):
                cell.number_format = "0"
            elif isinstance(val, float):
                cell.number_format = "0.00"

    # Freeze panes and add autofilter
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

