from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

from .schemas import LISTING_COLUMNS

DEFAULT_SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parent.parent / "config" / "service_account.json"
DEFAULT_SHEETS_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "sheets.local.yml"


class SheetSettings(BaseModel):
    spreadsheet_id: str
    worksheet_name: str = Field(default="V1")
    log_worksheet_name: str = Field(default="request_log")
    header_row: int = Field(default=1, ge=1)
    area_tolerance: float = Field(default=2.0, ge=0)
    name_threshold: float = Field(default=0.82, ge=0, le=1)
    batch_size: int = Field(default=50, ge=1)


class AppSettings(BaseModel):
    service_account_file: Path = Field(default=DEFAULT_SERVICE_ACCOUNT_FILE)
    sheet: SheetSettings


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


def load_settings(
    *,
    env: Optional[dict[str, str]] = None,
    sheets_config_path: Optional[Path] = None,
) -> AppSettings:
    env_map = env or os.environ
    if sheets_config_path is None:
        cfg_path = env_map.get("CRM_SHEETS_CONFIG")
        sheets_config_path = Path(cfg_path) if cfg_path else DEFAULT_SHEETS_CONFIG_FILE

    sheet_data = _load_yaml(sheets_config_path)
    sheet_cfg = (sheet_data.get("sheets") or {}).get("listings") or {}

    service_account_path = env_map.get("CRM_SERVICE_ACCOUNT_FILE", str(DEFAULT_SERVICE_ACCOUNT_FILE))

    overrides = {
        "spreadsheet_id": env_map.get("CRM_SHEET_ID", sheet_cfg.get("spreadsheet_id")),
        "worksheet_name": env_map.get("CRM_SHEET_NAME", sheet_cfg.get("worksheet", sheet_cfg.get("worksheet_name", "V1"))),
        "log_worksheet_name": env_map.get("CRM_LOG_SHEET_NAME", sheet_cfg.get("log_worksheet_name", "request_log")),
        "header_row": int(env_map.get("CRM_HEADER_ROW", sheet_cfg.get("header_row", 1))),
        "area_tolerance": float(env_map.get("CRM_MATCH_AREA_TOLERANCE", sheet_cfg.get("match", {}).get("tolerance_sqm", sheet_cfg.get("area_tolerance", 2.0)))),
        "name_threshold": float(env_map.get("CRM_MATCH_NAME_THRESHOLD", sheet_cfg.get("match", {}).get("name_threshold", sheet_cfg.get("name_threshold", 0.82)))),
        "batch_size": int(env_map.get("CRM_BATCH_SIZE", sheet_cfg.get("batch_size", 50))),
    }

    sheet_settings = SheetSettings(**overrides)

    return AppSettings(service_account_file=Path(service_account_path), sheet=sheet_settings)


__all__ = [
    "AppSettings",
    "SheetSettings",
    "load_settings",
    "LISTING_COLUMNS",
]
