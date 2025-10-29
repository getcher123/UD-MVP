from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2] / "app-crm"
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

from app_crm.config import SheetSettings
from app_crm.schemas import ImportListingsRequest, ListingPayload
from app_crm.service import CRMProcessor
from app_crm.sheet_gateway import MemorySheetGateway

DEFAULT_SETTINGS = SheetSettings(
    spreadsheet_id="dummy",
    worksheet_name="V1",
    header_row=1,
    area_tolerance=5.0,
)


def build_processor(gateway: MemorySheetGateway) -> CRMProcessor:
    return CRMProcessor(DEFAULT_SETTINGS, gateway)


def make_request(request_id: str, **listing_fields):
    listing = ListingPayload(**listing_fields)
    return ImportListingsRequest(request_id=request_id, listings=[listing])


def test_insert_new_listing():
    gateway = MemorySheetGateway()
    processor = build_processor(gateway)

    request = make_request(
        "req-1",
        building_name="CRM Core XP Tower 1",
        area_sqm=220,
        rent_rate_year_sqm_base=20000,
    )

    response = processor.process(request)

    assert response.summary.inserted == 1
    assert response.sheet_url.endswith(DEFAULT_SETTINGS.spreadsheet_id)
    assert response.summary.updated == 0
    assert len(gateway.rows) == 1
    stored = gateway.rows[0].data
    assert stored["building_name"] == "CRM Core XP Tower 1"
    assert stored["area_sqm"] == 220
    assert stored["request_id"] == "req-1"


def test_insert_with_minimal_columns():
    gateway = MemorySheetGateway()
    processor = build_processor(gateway)

    request = ImportListingsRequest(
        request_id="req-minimal",
        listings=[
            ListingPayload(
                building_name="CRM Core XP Tower minimal",
                area_sqm=180,
            )
        ],
    )

    response = processor.process(request)

    assert response.summary.inserted == 1
    assert response.sheet_url.endswith(DEFAULT_SETTINGS.spreadsheet_id)
    stored = gateway.rows[0].data
    assert stored["building_name"] == "CRM Core XP Tower minimal"
    assert stored["area_sqm"] == 180
    assert stored["request_id"] == "req-minimal"


def test_update_existing_listing_matches_by_area():
    gateway = MemorySheetGateway()
    processor = build_processor(gateway)

    # Seed an existing row
    seed_values = [
        "Office",
        "CRM Core XP Tower 2",
        "Офис",
        250,
        180,
        "2 этаж",
        "Аренда",
        "С отделкой",
        "Готово",
        21000,
        "С НДС",
        2500,
        "Да",
        450000,
        0,
        "",
        "seed.pdf",
        "seed-req",
        "Initial row",
        "[]",
        datetime.utcnow().isoformat() + "Z",
    ]
    gateway.append_row(seed_values)

    request = make_request(
        "req-2",
        building_name="CRM Core XP Tower 2",
        area_sqm=249.5,
        rent_rate_year_sqm_base=23000,
        rent_month_total_gross=480000,
    )

    response = processor.process(request)

    assert response.summary.updated == 1
    assert response.sheet_url.endswith(DEFAULT_SETTINGS.spreadsheet_id)
    assert response.summary.inserted == 0
    stored = gateway.rows[0].data
    assert stored["rent_rate_year_sqm_base"] == 23000
    assert stored["rent_month_total_gross"] == 480000
    assert stored["request_id"] == "req-2"


def test_duplicates_marked_when_multiple_matches():
    gateway = MemorySheetGateway()
    processor = build_processor(gateway)

    values = [
        "Office",
        "CRM Core XP Tower 3",
        "Офис",
        200,
        150,
        "3 этаж",
        "Аренда",
        "С отделкой",
        "Готово",
        20000,
        "С НДС",
        2500,
        "Да",
        400000,
        0,
        "",
        "file1.pdf",
        "r1",
        "Row 1",
        "[]",
        datetime.utcnow().isoformat() + "Z",
    ]
    gateway.append_row(values)
    values[3] = 201
    gateway.append_row(values)

    request = make_request(
        "req-3",
        building_name="CRM Core XP Tower 3",
        area_sqm=200.5,
    )

    response = processor.process(request)

    assert response.summary.skipped == 1
    assert response.summary.updated == 0
    assert response.duplicates and response.duplicates[0].listing_index == 0


def test_idempotent_requests_return_cached_summary():
    gateway = MemorySheetGateway()
    processor = build_processor(gateway)

    request = make_request(
        "req-4",
        building_name="CRM Core XP Tower 4",
        area_sqm=210,
    )

    first = processor.process(request)
    second = processor.process(request)

    assert first.summary.inserted == 1
    assert second.summary.inserted == 1  # cached summary should match first run
    assert first.sheet_url == second.sheet_url == processor.sheet_url
    assert len(gateway.rows) == 1
    assert gateway.find_request_log("req-4") is not None
