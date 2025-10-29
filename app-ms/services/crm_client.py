from __future__ import annotations

from typing import Any, Mapping

import httpx

from core.config import Settings
from core.errors import ErrorCode, ServiceError


def send_listings_to_crm(payload: Mapping[str, Any], settings: Settings) -> dict[str, Any]:
    if not settings.APP_CRM_URL:
        raise ServiceError(ErrorCode.CRM_SYNC_ERROR, 500, "APP_CRM_URL is not configured")

    try:
        response = httpx.post(
            settings.APP_CRM_URL,
            json=payload,
            timeout=settings.APP_CRM_TIMEOUT,
        )
    except httpx.RequestError as exc:  # pragma: no cover - network failure
        raise ServiceError(ErrorCode.CRM_SYNC_ERROR, 424, f"app-crm request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        raise ServiceError(
            ErrorCode.CRM_SYNC_ERROR,
            response.status_code,
            f"app-crm returned {response.status_code}: {detail}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ServiceError(ErrorCode.CRM_SYNC_ERROR, 424, f"Invalid JSON from app-crm: {exc}") from exc

    if not isinstance(data, dict):
        raise ServiceError(ErrorCode.CRM_SYNC_ERROR, 424, "app-crm payload is not an object")

    return data


__all__ = ["send_listings_to_crm"]
