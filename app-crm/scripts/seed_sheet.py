"""
Populate the CRM Google Sheet with deterministic smoke-test data.

The script reads connection settings from `sheets.local.yml` and uses the
service account JSON stored in `config/service_account.json`. It appends
several rows that can be used for manual or automated smoke-tests.

Example (PowerShell):
    python app-crm/scripts/seed_sheet.py --truncate
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import uuid
from pathlib import Path
from typing import Iterable, Sequence

import gspread
import yaml
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

DEFAULT_SERVICE_ACCOUNT = Path(__file__).resolve().parent.parent / "config" / "service_account.json"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "sheets.local.yml"
DEFAULT_HEADER = [
    "object_name",
    "building_name",
    "use_type_norm",
    "area_sqm",
    "divisible_from_sqm",
    "floors_norm",
    "market_type",
    "fitout_condition_norm",
    "delivery_date_norm",
    "rent_rate_year_sqm_base",
    "rent_vat_norm",
    "opex_year_per_sqm",
    "opex_included",
    "rent_month_total_gross",
    "sale_price_per_sqm",
    "sale_vat_norm",
    "source_file",
    "request_id",
    "recognition_summary",
    "uncertain_parameters",
    "updated_at",
]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Google Sheet with smoke-test data.")
    parser.add_argument(
        "--service-account",
        type=Path,
        default=DEFAULT_SERVICE_ACCOUNT,
        help=f"Path to service account JSON (default: {DEFAULT_SERVICE_ACCOUNT})",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to sheets config YAML (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Remove all existing rows below the header before inserting samples.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="How many sample rows to append (default: 5).",
    )
    return parser.parse_args(argv)


def load_credentials(service_account_path: Path) -> Credentials:
    if not service_account_path.exists():
        raise FileNotFoundError(f"Service account file not found: {service_account_path}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    return Credentials.from_service_account_file(str(service_account_path), scopes=scopes)


def load_sheet_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Sheets config not found: {config_path}. "
            "Copy sheets.example.yml to sheets.local.yml and fill it in."
        )

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    try:
        listings = data["sheets"]["listings"]
    except (KeyError, TypeError) as exc:
        raise KeyError("Missing `sheets.listings` configuration in sheets config") from exc
    return listings


def authorize(creds: Credentials, spreadsheet_id: str, worksheet_name: str):
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    return worksheet


def truncate_worksheet(worksheet, header_row: int) -> None:
    start_row = header_row + 1
    if start_row > worksheet.row_count:
        return

    start_cell = rowcol_to_a1(start_row, 1)
    end_col = max(worksheet.col_count, 26)  # default to at least column Z
    end_row = max(worksheet.row_count, start_row)
    end_cell = rowcol_to_a1(end_row, end_col)
    worksheet.batch_clear([f"{start_cell}:{end_cell}"])


def ensure_header(worksheet, header_row: int, default_header: Sequence[str]) -> list[str]:
    values = worksheet.row_values(header_row)
    if values:
        return values

    worksheet.update(f"A{header_row}", [list(default_header)])
    return list(default_header)


def generate_sample_rows(count: int) -> Iterable[dict[str, object]]:
    base_time = dt.datetime.utcnow().replace(microsecond=0)
    for idx in range(count):
        listing_index = idx + 1
        area = 200 + 25 * listing_index
        divisible = max(100, area - 80)
        rent = 20000 + listing_index * 1500
        opex = 2500 + listing_index * 120
        sale_price = 180000 + listing_index * 5000
        yield {
            "object_name": f"Смок-тест, помещение {listing_index}",
            "building_name": f"CRM Core XP Tower {listing_index}",
            "use_type_norm": "Офис",
            "area_sqm": area,
            "divisible_from_sqm": divisible,
            "floors_norm": f"{listing_index} этаж",
            "market_type": "Аренда",
            "fitout_condition_norm": "С отделкой" if listing_index % 2 else "Без отделки",
            "delivery_date_norm": "Готово",
            "rent_rate_year_sqm_base": rent,
            "rent_vat_norm": "С НДС",
            "opex_year_per_sqm": opex,
            "opex_included": "Да",
            "rent_month_total_gross": round((rent + opex) * area / 12, 2),
            "sale_price_per_sqm": sale_price,
            "sale_vat_norm": "С НДС" if listing_index % 2 else "Без НДС",
            "source_file": f"smoke_test_{listing_index:02d}.pdf",
            "request_id": str(uuid.uuid4()),
            "recognition_summary": f"Smoke test row #{listing_index}",
            "uncertain_parameters": "[]",
            "updated_at": (base_time + dt.timedelta(minutes=listing_index)).isoformat() + "Z",
        }


def to_rows_dict(header: Sequence[str], samples: Iterable[dict[str, object]]) -> list[list[object]]:
    rows: list[list[object]] = []
    for sample in samples:
        row = [sample.get(column, "") for column in header]
        rows.append(row)
    return rows


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    listings_cfg = load_sheet_config(args.config)
    spreadsheet_id = listings_cfg["spreadsheet_id"]
    worksheet_name = listings_cfg.get("worksheet", "V1")
    header_row = int(listings_cfg.get("header_row", 1))

    creds = load_credentials(args.service_account)
    worksheet = authorize(creds, spreadsheet_id, worksheet_name)

    header = ensure_header(worksheet, header_row, DEFAULT_HEADER)

    if args.truncate:
        truncate_worksheet(worksheet, header_row)
        print(f"Cleared rows below header in worksheet '{worksheet_name}'.")
        header = ensure_header(worksheet, header_row, DEFAULT_HEADER)

    samples = list(generate_sample_rows(args.samples))
    rows = to_rows_dict(header, samples)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"Inserted {len(rows)} sample rows into '{worksheet_name}'.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
