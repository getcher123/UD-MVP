import base64
import sys
from pathlib import Path

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

import pytest

from core.config import Settings
from core.errors import ErrorCode, ServiceError
from services import audio_client


class DummyResponse:
    def __init__(self, status_code: int = 200, json_data=None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


def _make_settings(**overrides):
    return Settings(**overrides)


def test_transcribe_audio_success(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):  # noqa: ANN001
        captured.update({"url": url, "json": json, "timeout": timeout})
        return DummyResponse(json_data={"srt": "1\n00:00:00,000 --> 00:00:01,000\nspeaker1: hi"})

    monkeypatch.setattr(audio_client.httpx, "post", fake_post)

    settings = _make_settings(APP_AUDIO_URL="http://audio", APP_AUDIO_TIMEOUT=12)
    result = audio_client.transcribe_audio(b"audio-bytes", "sample.wav", settings)

    assert result["srt"].startswith("1\n00:00")
    assert captured["url"] == "http://audio"
    assert captured["timeout"] == 12
    assert base64.b64decode(captured["json"]["audio_base64"]) == b"audio-bytes"
    assert captured["json"]["settings"]["diar"] is True


def test_transcribe_audio_error_status(monkeypatch):
    def fake_post(url, json, timeout):  # noqa: ANN001
        return DummyResponse(status_code=500, text="boom")

    monkeypatch.setattr(audio_client.httpx, "post", fake_post)

    settings = _make_settings(APP_AUDIO_URL="http://audio")
    with pytest.raises(ServiceError) as exc:
        audio_client.transcribe_audio(b"x", "a.wav", settings)
    assert exc.value.code == ErrorCode.TRANSCRIPTION_ERROR
