from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, RootModel, ValidationError, model_validator

LISTING_COLUMNS: list[str] = [
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


class ListingPayload(BaseModel):
    object_name: Optional[str] = None
    building_name: str
    use_type_norm: Optional[str] = None
    area_sqm: Optional[float] = None
    divisible_from_sqm: Optional[float] = None
    floors_norm: Optional[str] = None
    market_type: Optional[str] = None
    fitout_condition_norm: Optional[str] = None
    delivery_date_norm: Optional[str] = None
    rent_rate_year_sqm_base: Optional[float] = None
    rent_vat_norm: Optional[str] = None
    opex_year_per_sqm: Optional[float] = None
    opex_included: Optional[str] = None
    rent_month_total_gross: Optional[float] = None
    sale_price_per_sqm: Optional[float] = None
    sale_vat_norm: Optional[str] = None
    source_file: Optional[str] = None
    request_id: Optional[str] = None
    recognition_summary: Optional[str] = None
    uncertain_parameters: Optional[List[Any]] = None

    @model_validator(mode="after")
    def ensure_area(cls, values: "ListingPayload") -> "ListingPayload":
        # Area may be optional but for matching we rely on it; leave validation to service.
        return values


class ImportListingsRequest(BaseModel):
    request_id: str = Field(..., min_length=1)
    source_file: Optional[str] = None
    received_at: Optional[str] = None
    listings: List[ListingPayload]
    meta: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_at_least_one_listing(cls, values: "ImportListingsRequest") -> "ImportListingsRequest":
        if not values.listings:
            raise ValueError("listings must contain at least one item")
        return values


class SummaryPayload(BaseModel):
    updated: int = 0
    inserted: int = 0
    skipped: int = 0


class DuplicateEntry(BaseModel):
    listing_index: int
    reason: str


class ImportListingsResponse(BaseModel):
    request_id: str
    processed_at: str
    summary: SummaryPayload
    duplicates: List[DuplicateEntry] = Field(default_factory=list)
