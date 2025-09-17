from __future__ import annotations

import base64
from typing import Any, Dict

import httpx

from core.config import Settings
from core.errors import ErrorCode, ServiceError


def _build_payload(audio_bytes: bytes, filename: str, settings: Settings) -> Dict[str, Any]:
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    req_settings: Dict[str, Any] = {"diar": True}
    if settings.APP_AUDIO_LANGUAGE:
        req_settings["language"] = settings.APP_AUDIO_LANGUAGE
    if settings.APP_AUDIO_MODEL:
        req_settings["whisper_model"] = settings.APP_AUDIO_MODEL

    return {
        "audio_base64": encoded,
        "filename": filename,
        "settings": req_settings,
    }


def transcribe_audio(audio_bytes: bytes, filename: str, settings: Settings) -> Dict[str, Any]:
    if not settings.APP_AUDIO_URL:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, "APP_AUDIO_URL is not configured")

    payload = _build_payload(audio_bytes, filename, settings)

    try:
        response = httpx.post(
            settings.APP_AUDIO_URL,
            json=payload,
            timeout=settings.APP_AUDIO_TIMEOUT,
        )
    except httpx.RequestError as exc:  # pragma: no cover - network failure
        raise ServiceError(ErrorCode.TRANSCRIPTION_ERROR, 424, f"app-audio request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        raise ServiceError(
            ErrorCode.TRANSCRIPTION_ERROR,
            424,
            f"app-audio returned {response.status_code}: {detail}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ServiceError(ErrorCode.TRANSCRIPTION_ERROR, 424, f"Invalid JSON from app-audio: {exc}") from exc

    if not isinstance(data, dict):
        raise ServiceError(ErrorCode.TRANSCRIPTION_ERROR, 424, "app-audio payload is not an object")

    return data


__all__ = ["transcribe_audio"]
