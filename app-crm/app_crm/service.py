from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional

from .config import SheetSettings
from .schemas import (
    ImportListingsRequest,
    ImportListingsResponse,
    ListingPayload,
    SummaryPayload,
    DuplicateEntry,
    LISTING_COLUMNS,
)
from .sheet_gateway import SheetGateway, SheetRow


class CRMProcessor:
    def __init__(
        self,
        sheet_settings: SheetSettings,
        sheet_gateway: SheetGateway,
        *,
        columns: Iterable[str] = LISTING_COLUMNS,
    ) -> None:
        self.settings = sheet_settings
        self.gateway = sheet_gateway
        self.columns = list(columns)
        self.sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_settings.spreadsheet_id}"

    def process(self, payload: ImportListingsRequest) -> ImportListingsResponse:
        cached = self.gateway.find_request_log(payload.request_id)
        if cached:
            return ImportListingsResponse(
                request_id=payload.request_id,
                processed_at=cached.get("processed_at"),
                sheet_url=self.sheet_url,
                summary=SummaryPayload(**cached.get("summary", {})),
                duplicates=[DuplicateEntry(**item) for item in cached.get("duplicates", [])],
            )

        existing = self.gateway.fetch_rows()
        index = self._build_index(existing)

        processed_at = datetime.now(timezone.utc).isoformat()
        summary = SummaryPayload()
        duplicates: list[DuplicateEntry] = []

        for idx, listing in enumerate(payload.listings):
            result = self._process_listing(idx, listing, payload, processed_at, index)
            if result == "inserted":
                summary.inserted += 1
            elif result == "updated":
                summary.updated += 1
            elif result == "duplicate":
                duplicates.append(
                    DuplicateEntry(
                        listing_index=idx,
                        reason="multiple sheet matches (ambiguous area)",
                    )
                )
                summary.skipped += 1
            else:
                summary.skipped += 1

        log_payload = {
            "summary": summary.model_dump(),
            "duplicates": [dup.model_dump() for dup in duplicates],
            "processed_at": processed_at,
        }
        self.gateway.write_request_log(payload.request_id, log_payload)

        return ImportListingsResponse(
            request_id=payload.request_id,
            processed_at=processed_at,
            sheet_url=self.sheet_url,
            summary=summary,
            duplicates=duplicates,
        )

    def _process_listing(
        self,
        idx: int,
        listing: ListingPayload,
        payload: ImportListingsRequest,
        processed_at: str,
        index: dict[str, list[SheetRow]],
    ) -> str:
        building_key = listing.building_name.strip().lower()
        area = _coerce_float(listing.area_sqm)

        if not building_key or area is None or area <= 0:
            return "skipped"

        candidates = index.get(building_key, [])
        tolerance = self.settings.area_tolerance
        matching = [
            row
            for row in candidates
            if _coerce_float(row.data.get("area_sqm")) is not None
            and abs(_coerce_float(row.data.get("area_sqm")) - area) <= tolerance
        ]

        values = self._listing_to_row(listing, payload, processed_at)

        if not matching:
            row_index = self.gateway.append_row(values)
            index.setdefault(building_key, []).append(
                SheetRow(row_index=row_index if isinstance(row_index, int) else -1, data=self._row_to_dict(values))
            )
            return "inserted"

        if len(matching) > 1:
            return "duplicate"

        target_row = matching[0]
        self.gateway.update_row(target_row.row_index, values)
        target_row.data = self._row_to_dict(values)
        return "updated"

    def _listing_to_row(
        self,
        listing: ListingPayload,
        payload: ImportListingsRequest,
        processed_at: str,
    ) -> list[Any]:
        data = listing.model_dump()
        data["request_id"] = payload.request_id
        if not data.get("source_file"):
            data["source_file"] = payload.source_file
        data["updated_at"] = processed_at
        if isinstance(data.get("uncertain_parameters"), list):
            data["uncertain_parameters"] = json_dumps(data["uncertain_parameters"])
        return [data.get(column, "") for column in self.columns]

    def _row_to_dict(self, values: list[Any]) -> dict[str, Any]:
        return {column: value for column, value in zip(self.columns, values)}

    def _build_index(self, rows: list[SheetRow]) -> dict[str, list[SheetRow]]:
        index: dict[str, list[SheetRow]] = {}
        for row in rows:
            building_name = (row.data.get("building_name") or "").strip().lower()
            index.setdefault(building_name, []).append(row)
        return index


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
