"""FastAPI service for audio transcription."""
from __future__ import annotations

import base64
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

import torch
import types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator

import whisper

# Disable RNN flattening to avoid fork-related errors when using torch on CPU.
for rnn in (torch.nn.LSTM, torch.nn.GRU, torch.nn.RNN):
    rnn.flatten_parameters = types.MethodType(lambda self, *_, **__: None, rnn)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Audio Transcription Service", version="0.1.0")


def _select_device() -> str:
    """Detect compute device based on environment overrides and CUDA availability."""

    override = os.environ.get("TORCH_DEVICE")
    if override:
        logger.info("Using TORCH_DEVICE override: %s", override)
        return override

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return device


class TranscriptionSettings(BaseModel):
    """User-controlled recognition options."""

    language: Optional[str] = Field(
        default=None,
        description="Language code forced for the Whisper model (e.g. 'ru', 'en').",
    )
    whisper_model: str = Field(
        default="large-v3",
        description="Name of the Whisper model to use.",
    )
    translate: bool = Field(
        default=False,
        description="When true, Whisper translates speech to English instead of transcribing.",
    )


class TranscriptionRequest(BaseModel):
    """Incoming payload for the transcription endpoint."""

    audio_base64: str = Field(..., description="Base64 encoded audio file content.")
    filename: Optional[str] = Field(
        default=None,
        description="Original filename — used only to keep the extension when writing a temp file.",
    )
    settings: TranscriptionSettings = Field(
        default_factory=TranscriptionSettings,
        description="Recognition settings the caller can tweak.",
    )

    @validator("audio_base64")
    def validate_audio(cls, value: str) -> str:  # noqa: D401
        """Ensure audio payload is not empty."""
        if not value or not value.strip():
            raise ValueError("audio_base64 must not be empty")
        return value


class TranscriptionResponse(BaseModel):
    """Payload returned after the audio has been processed."""

    text: str = Field(..., description="Recognised text produced by Whisper.")
    language: Optional[str] = Field(
        default=None,
        description="Language detected or forced during transcription.",
    )
    segments: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-segment metadata returned by Whisper (timestamps, probabilities).",
    )


@lru_cache(maxsize=2)
def load_model(model_name: str):
    """Load and cache Whisper models so we don't reload on every request."""

    device = _select_device()
    logger.info("Loading Whisper model %s on %s", model_name, device)
    try:
        model = whisper.load_model(model_name, device=device)
    except Exception as exc:  # pragma: no cover - defensive, depends on env
        logger.exception("Failed to load Whisper model %s", model_name)
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load Whisper model '{model_name}': {exc}",
        ) from exc

    try:
        actual_device = str(next(model.parameters()).device)
    except Exception:  # pragma: no cover - implementation detail
        actual_device = device

    if actual_device != device:
        logger.info(
            "Whisper model %s initialised on %s (requested %s)",
            model_name,
            actual_device,
            device,
        )
    else:
        logger.info("Whisper model %s initialised on %s", model_name, actual_device)

    return model


def _decode_audio_to_tempfile(audio_base64: str, filename: Optional[str]) -> Path:
    """Persist the base64-encoded audio payload into a temporary file."""

    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as exc:  # pragma: no cover - malformed client payload
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}") from exc

    suffix = ""
    if filename:
        suffix = "".join(Path(filename).suffixes) or suffix

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_bytes)
            return Path(temp_file.name)
    except Exception as exc:  # pragma: no cover - filesystem specific
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write audio temporary file: {exc}",
        ) from exc


@app.post("/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(payload: TranscriptionRequest) -> TranscriptionResponse:
    """Decode incoming audio and run Whisper to obtain the transcript."""

    temp_path: Optional[Path] = None
    result: dict[str, Any] = {}
    try:
        temp_path = _decode_audio_to_tempfile(payload.audio_base64, payload.filename)
        settings = payload.settings
        model = load_model(settings.whisper_model)
        result = model.transcribe(
            str(temp_path),
            language=settings.language,
            task="translate" if settings.translate else "transcribe",
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - model/runtime errors
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:  # pragma: no cover - cleanup best-effort
                logger.warning("Failed to remove temporary file %s", temp_path, exc_info=True)

    return TranscriptionResponse(
        text=result.get("text", "").strip(),
        language=result.get("language", payload.settings.language),
        segments=list(result.get("segments", [])),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple readiness probe."""

    return {"status": "ok"}
