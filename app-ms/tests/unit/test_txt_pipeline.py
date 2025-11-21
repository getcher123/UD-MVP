from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

from main import app
from api import routes_process  # type: ignore  # noqa: E402


def test_txt_pipeline_uses_raw_text(monkeypatch):
    captured: dict[str, str] = {}

    def fake_extract(text: str):  # noqa: ANN001
        captured["text"] = text
        return {"objects": []}

    def fake_normalize(payload, rules):  # noqa: ANN001
        captured["payload"] = payload
        return ([], [])

    def fake_flatten(objects, rules, request_id, source_file):  # noqa: ANN001
        captured["flatten_called"] = "1"
        return []

    monkeypatch.setattr(routes_process, "extract_structured_objects", fake_extract)
    monkeypatch.setattr(routes_process, "normalize_agentql_payload", fake_normalize)
    monkeypatch.setattr(routes_process, "flatten_objects_to_listings", fake_flatten)

    client = TestClient(app)
    resp = client.post(
        "/process_file",
        data={"output": "json"},
        files={"file": ("note.txt", b"hello world", "text/plain")},
    )

    assert resp.status_code == 200
    assert captured["text"] == "hello world"
