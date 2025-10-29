from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional, Protocol

import gspread
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1

from .config import AppSettings, SheetSettings
from .schemas import LISTING_COLUMNS


@dataclass
class SheetRow:
    row_index: int
    data: dict[str, Any]


class SheetGateway(Protocol):
    def fetch_rows(self) -> List[SheetRow]:
        ...

    def update_row(self, row_index: int, values: List[Any]) -> None:
        ...

    def append_row(self, values: List[Any]) -> int:
        ...

    def find_request_log(self, request_id: str) -> Optional[dict[str, Any]]:
        ...

    def write_request_log(self, request_id: str, payload: dict[str, Any]) -> None:
        ...


class GspreadSheetGateway:
    def __init__(self, client: gspread.Client, settings: SheetSettings, columns: Iterable[str] = LISTING_COLUMNS):
        self._client = client
        self._settings = settings
        self._columns = list(columns)

        spreadsheet = self._client.open_by_key(settings.spreadsheet_id)
        self._worksheet = spreadsheet.worksheet(settings.worksheet_name)
        try:
            self._log_worksheet = spreadsheet.worksheet(settings.log_worksheet_name)
        except WorksheetNotFound:
            self._log_worksheet = spreadsheet.add_worksheet(
                title=settings.log_worksheet_name,
                rows=100,
                cols=4,
            )
        self._ensure_log_headers()

    def _ensure_log_headers(self) -> None:
        headers = self._log_worksheet.row_values(1)
        expected = ["request_id", "summary", "duplicates", "processed_at"]
        if headers != expected:
            self._log_worksheet.update("A1", [expected])

    def fetch_rows(self) -> List[SheetRow]:
        values = self._worksheet.get_all_values()
        header_row = self._settings.header_row
        rows: list[SheetRow] = []
        for idx, row_values in enumerate(values[header_row:], start=header_row + 1):
            if not any(cell.strip() for cell in row_values):
                continue
            mapped = self._row_to_dict(row_values)
            rows.append(SheetRow(row_index=idx, data=mapped))
        return rows

    def _row_to_dict(self, row_values: list[str]) -> dict[str, Any]:
        data = {}
        for col, value in zip(self._columns, row_values):
            data[col] = value
        return data

    def update_row(self, row_index: int, values: List[Any]) -> None:
        start_cell = rowcol_to_a1(row_index, 1)
        self._worksheet.update(start_cell, [values], value_input_option="USER_ENTERED")

    def append_row(self, values: List[Any]) -> int:
        result = self._worksheet.append_row(values, value_input_option="USER_ENTERED")
        updated_range = result.get("updates", {}).get("updatedRange")
        if isinstance(updated_range, str):
            try:
                row_part = updated_range.split("!")[1].split(":")[0]
                row_number = int("".join(filter(str.isdigit, row_part)))
                return row_number
            except (IndexError, ValueError):
                pass
        return self._worksheet.row_count

    def find_request_log(self, request_id: str) -> Optional[dict[str, Any]]:
        records = self._log_worksheet.get_all_records()
        for record in records:
            if record.get("request_id") == request_id:
                try:
                    summary = json.loads(record.get("summary") or "{}")
                except json.JSONDecodeError:
                    summary = {}
                try:
                    duplicates = json.loads(record.get("duplicates") or "[]")
                except json.JSONDecodeError:
                    duplicates = []
                return {
                    "summary": summary,
                    "duplicates": duplicates,
                    "processed_at": record.get("processed_at"),
                }
        return None

    def write_request_log(self, request_id: str, payload: dict[str, Any]) -> None:
        row = [
            request_id,
            json.dumps(payload.get("summary", {}), ensure_ascii=False),
            json.dumps(payload.get("duplicates", []), ensure_ascii=False),
            payload.get("processed_at") or datetime.utcnow().isoformat() + "Z",
        ]
        self._log_worksheet.append_row(row, value_input_option="USER_ENTERED")


class MemorySheetGateway:
    def __init__(self, columns: Iterable[str] = LISTING_COLUMNS):
        self.columns = list(columns)
        self.rows: list[SheetRow] = []
        self.logs: dict[str, dict[str, Any]] = {}
        self._next_row = 2

    def fetch_rows(self) -> List[SheetRow]:
        return list(self.rows)

    def update_row(self, row_index: int, values: List[Any]) -> None:
        mapped = {col: val for col, val in zip(self.columns, values)}
        for row in self.rows:
            if row.row_index == row_index:
                row.data = mapped
                return
        self.rows.append(SheetRow(row_index=row_index, data=mapped))

    def append_row(self, values: List[Any]) -> int:
        row_index = self._next_row
        self._next_row += 1
        mapped = {col: val for col, val in zip(self.columns, values)}
        self.rows.append(SheetRow(row_index=row_index, data=mapped))
        return row_index

    def find_request_log(self, request_id: str) -> Optional[dict[str, Any]]:
        return self.logs.get(request_id)

    def write_request_log(self, request_id: str, payload: dict[str, Any]) -> None:
        self.logs[request_id] = payload
