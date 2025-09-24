#!/usr/bin/env python
"""Apply uniform borders to all used cells in an Excel workbook via UNO."""

import math
import os
import sys
from pathlib import Path

try:
    import uno  # type: ignore
    import unohelper  # type: ignore
    import officehelper  # type: ignore
    from com.sun.star.beans import PropertyValue  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"UNO libraries unavailable: {exc}")


def _create_border(line_width_pt: float):
    border = uno.createUnoStruct('com.sun.star.table.BorderLine2')
    border.LineWidth = int(round(line_width_pt * 35.28))
    border.LineStyle = uno.getConstantByName('com.sun.star.table.BorderLineStyle.SOLID')
    return border


def _get_used_range(sheet):
    cursor = sheet.createCursor()
    cursor.gotoStartOfUsedArea(False)
    cursor.gotoEndOfUsedArea(True)
    addr = cursor.RangeAddress
    if addr.EndColumn < addr.StartColumn or addr.EndRow < addr.StartRow:
        return None
    return sheet.getCellRangeByPosition(addr.StartColumn, addr.StartRow, addr.EndColumn, addr.EndRow)


def apply_borders(document, line_width_pt: float) -> None:
    border_line = _create_border(line_width_pt)
    for sheet in document.Sheets:
        used = _get_used_range(sheet)
        if used is None:
            continue
        cols = used.Columns.getCount()
        rows = used.Rows.getCount()
        for c in range(cols):
            for r in range(rows):
                cell = used.getCellByPosition(c, r)
                cell.TopBorder = border_line
                cell.BottomBorder = border_line
                cell.LeftBorder = border_line
                cell.RightBorder = border_line


def load_document(ctx, file_url: str):
    desktop = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
    props = (PropertyValue(Name='Hidden', Value=True),)
    return desktop.loadComponentFromURL(file_url, '_blank', 0, props)


def save_document(document, out_url: str) -> None:
    props = (PropertyValue(Name='FilterName', Value='Calc MS Excel 2007 XML'),)
    document.storeToURL(out_url, props)


def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: uno_set_borders.py <input.xlsx> <output.xlsx> [line_width_pt]', file=sys.stderr)
        return 1

    in_path = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()
    line_width_pt = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    ctx = officehelper.bootstrap()
    doc = load_document(ctx, unohelper.systemPathToFileUrl(os.fspath(in_path)))
    try:
        apply_borders(doc, line_width_pt)
        out_url = unohelper.systemPathToFileUrl(os.fspath(out_path))
        if out_path == in_path:
            doc.store()
        else:
            save_document(doc, out_url)
    finally:
        doc.close(True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
