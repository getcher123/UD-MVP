from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

from services.excel_to_csv import excel_to_csv_text


def test_excel_to_csv_text(tmp_path):
    workbook_path = Path(tmp_path) / "sample.xlsx"

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Main"
    ws1.append(["Name", "Area"])
    ws1.append(["Office", 120])

    ws2 = wb.create_sheet("Second")
    ws2.append(["Only", "Row"])

    wb.save(workbook_path)
    wb.close()

    csv_text = excel_to_csv_text(workbook_path)

    assert "# sheet: Main" in csv_text
    assert '"Name","Area"' in csv_text
    assert '"Office","120"' in csv_text
    assert "# sheet: Second" in csv_text
    assert csv_text.strip().endswith('"Only","Row"')
