from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.mark.parametrize("filename", ["listing.xlsx", "listings.xlsx"])
def test_crm_forward_trigger(monkeypatch, filename):
    from api import routes_process

    captured = {}

    def fake_prepare(path, request_id, source_file, rules):
        captured["prepared"] = (path, request_id, source_file)
        return {
            "request_id": request_id,
            "source_file": source_file,
            "listings": [{"building_name": "Test", "listings": []}],
            "meta": {"listings_total": 1},
        }

    def fake_send(payload, settings):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(routes_process, "prepare_crm_payload", fake_prepare)
    monkeypatch.setattr(routes_process, "send_listings_to_crm", fake_send)
    monkeypatch.setattr(routes_process, "_excel_has_listing_headers", lambda *args, **kwargs: True)

    client = TestClient(app)
    response = client.post(
        "/process_file",
        files={
            "file": (
                filename,
                io.BytesIO(b"dummy"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["pipeline"] == "crm_forward"
    assert captured["payload"]["request_id"] == body["request_id"]
    assert captured["prepared"][2] == filename
