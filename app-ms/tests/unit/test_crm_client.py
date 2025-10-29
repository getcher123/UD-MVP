from __future__ import annotations

import pytest

from core.config import Settings
from core.errors import ErrorCode, ServiceError
from services import crm_client


def test_send_listings_to_crm_success(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(crm_client.httpx, "post", fake_post)

    settings = Settings(APP_CRM_URL="http://crm.local/v1/import/listings", APP_CRM_TIMEOUT=15.0)
    payload = {"request_id": "req-123"}

    result = crm_client.send_listings_to_crm(payload, settings)

    assert result == {"ok": True}
    assert captured["url"] == "http://crm.local/v1/import/listings"
    assert captured["json"] is payload
    assert captured["timeout"] == 15.0


def test_send_listings_to_crm_http_error(monkeypatch):
    class FakeResponse:
        status_code = 503
        text = "Service unavailable"

        @staticmethod
        def json():
            return {}

    monkeypatch.setattr(crm_client.httpx, "post", lambda *args, **kwargs: FakeResponse())

    settings = Settings(APP_CRM_URL="http://crm.local/v1/import/listings")

    with pytest.raises(ServiceError) as exc:
        crm_client.send_listings_to_crm({"request_id": "req"}, settings)

    assert exc.value.code == ErrorCode.CRM_SYNC_ERROR


def test_send_listings_to_crm_requires_url():
    settings = Settings(APP_CRM_URL=None)

    with pytest.raises(ServiceError) as exc:
        crm_client.send_listings_to_crm({"request_id": "req"}, settings)

    assert exc.value.code == ErrorCode.CRM_SYNC_ERROR
