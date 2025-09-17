"""FastAPI wrapper around whisper-diarization's diarize.py."""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import List, Optional

import torch
import types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator

# Patch RNN flatten_parameters just like the Colab snippet
for rnn in (torch.nn.LSTM, torch.nn.GRU, torch.nn.RNN):
    rnn.flatten_parameters = types.MethodType(lambda self, *_, **__: None, rnn)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Whisper Diarization Service", version="0.1.0")

REPO_DIR = Path(__file__).resolve().parent / "whisper-diarization"
DEFAULT_LANGUAGE = "ru"
DEFAULT_MODEL = "medium"





class TranscriptionSettings(BaseModel):
    """Recognition settings forwarded to diarize.py."""

    language: str = Field(default=DEFAULT_LANGUAGE, description="Whisper language code (e.g. 'ru').")
    whisper_model: str = Field(default=DEFAULT_MODEL, description="Whisper model name, e.g. 'medium'.")


class TranscriptionRequest(BaseModel):
    """Payload accepted by the transcribe endpoint."""

    audio_base64: str = Field(..., description="Base64 encoded audio content.")
    filename: Optional[str] = Field(
        default=None,
        description="Suggested filename (used to preserve extension for diarize.py).",
    )
    settings: TranscriptionSettings = Field(
        default_factory=TranscriptionSettings,
        description="Parameters passed to diarize.py",
    )

    @validator("audio_base64")
    def _validate_audio(cls, value: str) -> str:  # noqa: D401
        if not value or not value.strip():
            raise ValueError("audio_base64 must not be empty")
        return value


class SpeakerTurn(BaseModel):
    """Single speaker replica extracted from diarization output."""

    speaker: str = Field(..., description="Speaker label (Speaker X).")
    start: float = Field(..., description="Start time in seconds.")
    end: float = Field(..., description="End time in seconds.")
    text: str = Field(..., description="Sentence text for this speaker segment.")


class TranscriptionResponse(BaseModel):
    """Result returned to the client."""

    text: str = Field(..., description="Full transcript text (concatenated).")
    model: str = Field(..., description="Whisper model that diarize.py used.")
    language: str = Field(..., description="Language supplied to diarize.py.")
    duration_ms: int = Field(..., description="Processing duration in milliseconds.")
    speakers: List[SpeakerTurn] = Field(
        default_factory=list,
        description="Ordered speaker segments parsed from diarization output.",
    )


def _ensure_repo() -> None:
    if not REPO_DIR.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "whisper-diarization repository is missing. Clone it via "
                "'git clone --depth 1 https://github.com/MahmoudAshraf97/whisper-diarization.git app-audio/whisper-diarization'"
            ),
        )


def _decode_audio(audio_b64: str, filename: Optional[str]) -> Path:
    try:
        payload = base64.b64decode(audio_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}") from exc

    suffix = ""
    if filename:
        suffix = "".join(Path(filename).suffixes)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(payload)
            return Path(handle.name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist audio: {exc}") from exc


def _run_diarize(audio_path: Path, settings: TranscriptionSettings) -> None:
    command = [
        sys.executable,
        str(REPO_DIR / "diarize.py"),
        "-a",
        str(audio_path),
        "--language",
        settings.language,
        "--whisper-model",
        settings.whisper_model,
    ]
    logger.info("Running diarize.py: %s", " ".join(command))
    result = subprocess.run(
        command,
        cwd=REPO_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("diarize.py failed: %s", result.stderr)
        raise HTTPException(status_code=500, detail="diarize.py failed to process audio")


def _parse_timestamp(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _parse_srt(srt_file: Path) -> List[SpeakerTurn]:
    """Parse diarization SRT output into speaker turns with normalized labels."""

    if not srt_file.exists():
        raise HTTPException(status_code=500, detail="Diarization output (.srt) not found")

    blocks: list[SpeakerTurn] = []
    label_map: dict[str, str] = {}
    next_index = 1

    content = srt_file.read_text(encoding="utf8", errors="ignore")
    for chunk in content.strip().split("\n\n"):
        lines = [line for line in (line.strip() for line in chunk.splitlines()) if line]
        if len(lines) < 3:
            continue
        time_line = lines[1]
        if "-->" not in time_line:
            continue
        start_str, end_str = [part.strip() for part in time_line.split("-->")]
        text_line = " ".join(lines[2:])
        if ":" in text_line:
            speaker_raw, utterance = text_line.split(":", 1)
            speaker_raw = speaker_raw.strip() or "Speaker"
            utterance = utterance.strip()
        else:
            speaker_raw = "Speaker"
            utterance = text_line.strip()
        if not utterance:
            continue

        if speaker_raw not in label_map:
            label_map[speaker_raw] = f"speaker{next_index}"
            next_index += 1
        speaker = label_map[speaker_raw]

        start = _parse_timestamp(start_str)
        end = _parse_timestamp(end_str)

        if blocks and blocks[-1].speaker == speaker:
            blocks[-1].text = f"{blocks[-1].text} {utterance}".strip()
            blocks[-1].end = end
        else:
            blocks.append(SpeakerTurn(speaker=speaker, start=start, end=end, text=utterance))
    return blocks


@app.post("/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(payload: TranscriptionRequest) -> TranscriptionResponse:
    """Decode audio, invoke diarize.py, return parsed transcript."""

    _ensure_repo()

    temp_path: Optional[Path] = None
    started_at = perf_counter()
    try:
        temp_path = _decode_audio(payload.audio_base64, payload.filename)
        _run_diarize(temp_path, payload.settings)
        srt_path = temp_path.with_suffix(".srt")
        speaker_turns = _parse_srt(srt_path)
        if not speaker_turns:
            raise HTTPException(status_code=500, detail="Diarization produced no speaker segments")
        text_combined = " ".join(turn.text for turn in speaker_turns).strip()
        duration_ms = int((perf_counter() - started_at) * 1000)
        return TranscriptionResponse(
            text=text_combined,
            model=payload.settings.whisper_model,
            language=payload.settings.language,
            duration_ms=duration_ms,
            speakers=speaker_turns,
        )
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                logger.warning("Failed to remove temp file %s", temp_path, exc_info=True)
        if temp_path:
            for ext in (".srt", ".json", ".txt"):
                artifact = temp_path.with_suffix(ext)
                if artifact.exists():
                    try:
                        artifact.unlink()
                    except Exception:
                        logger.warning("Failed to remove artifact %s", artifact, exc_info=True)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple readiness endpoint."""

    return {"status": "ok"}



