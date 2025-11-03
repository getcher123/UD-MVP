"""
Utility script to verify Google Sheets access using the CRM service account.

Example usage (PowerShell):
    python app-crm/scripts/test_append_sheet.py `
        --spreadsheet-id "<sheet-id>" `
        --sheet-name "V1"
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Sequence

import gspread
from google.oauth2.service_account import Credentials

DEFAULT_SERVICE_ACCOUNT = Path(__file__).resolve().parent.parent / "config" / "service_account.json"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append a test row to a Google Sheet using the CRM service account."
    )
    parser.add_argument(
        "--service-account",
        type=Path,
        default=DEFAULT_SERVICE_ACCOUNT,
        help=f"Path to service account JSON (default: {DEFAULT_SERVICE_ACCOUNT})",
    )
    parser.add_argument(
        "--spreadsheet-id",
        required=True,
        help="Spreadsheet ID (from https://docs.google.com/spreadsheets/d/<ID>/)",
    )
    parser.add_argument(
        "--sheet-name",
        required=True,
        help="Worksheet name, e.g. V1",
    )
    parser.add_argument(
        "--note",
        default="codex-test",
        help="Optional note stored in the appended row.",
    )
    return parser.parse_args(argv)


def load_credentials(service_account_path: Path) -> Credentials:
    if not service_account_path.exists():
        raise FileNotFoundError(
            f"Service account file not found: {service_account_path}. "
            "Make sure you copied the JSON into this path."
        )

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    return Credentials.from_service_account_file(str(service_account_path), scopes=scopes)


def append_test_row(
    creds: Credentials,
    spreadsheet_id: str,
    sheet_name: str,
    note: str,
) -> list[str]:
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    timestamp = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    row = [timestamp, note, "ok"]

    worksheet.append_row(row, value_input_option="USER_ENTERED")
    return row


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    creds = load_credentials(args.service_account)
    row = append_test_row(creds, args.spreadsheet_id, args.sheet_name, args.note)

    print("Appended row:", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
