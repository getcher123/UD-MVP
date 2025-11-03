from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from core.errors import ServiceError
from services.crm_payload import prepare_crm_payload


def _rules_stub() -> dict:
    return {
        "output": {
            "listing_columns": [
                "building_name|Здание",
                "area_sqm|Площадь, кв.м.",
                "opex_included|OPEX включен",
                "uncertain_parameters|Сомнительные параметры",
            ]
        }
    }


def _write_workbook(tmp_path: Path, rows: list[list]) -> Path:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    path = tmp_path / "listings.xlsx"
    wb.save(path)
    wb.close()
    return path


def test_prepare_crm_payload_parses_values(tmp_path):
    rows = [
        ["Здание", "Площадь, кв.м.", "OPEX включен", "Сомнительные параметры"],
        ["Башня А", 123.0, "включен", "rent_rate_year_sqm_base; opex_included"],
    ]
    excel_path = _write_workbook(tmp_path, rows)

    payload = prepare_crm_payload(str(excel_path), "req-1", "listings.xlsx", _rules_stub())

    assert payload["request_id"] == "req-1"
    assert payload["source_file"] == "listings.xlsx"
    assert payload["meta"]["listings_total"] == 1
    listing = payload["listings"][0]
    assert listing["building_name"] == "Башня А"
    assert listing["area_sqm"] == 123.0
    assert listing["opex_included"] == "включен"
    assert listing["request_id"] == "req-1"
    assert listing["source_file"] == "listings.xlsx"
    assert listing["uncertain_parameters"] == ["rent_rate_year_sqm_base", "opex_included"]


def test_prepare_crm_payload_converts_numeric_strings(tmp_path):
    rows = [
        ["Здание", "Площадь, кв.м."],
        ["Башня Б", "456,5"],
    ]
    excel_path = _write_workbook(tmp_path, rows)

    payload = prepare_crm_payload(str(excel_path), "req-2", "listings.xlsx", _rules_stub())

    listing = payload["listings"][0]
    assert pytest.approx(listing["area_sqm"]) == 456.5


def test_prepare_crm_payload_requires_building_name(tmp_path):
    rows = [
        ["Здание", "Площадь, кв.м."],
        ["", 200],
    ]
    excel_path = _write_workbook(tmp_path, rows)

    with pytest.raises(ServiceError):
        prepare_crm_payload(str(excel_path), "req-3", "listings.xlsx", _rules_stub())
