import json
from types import SimpleNamespace

import pytest

from core.errors import ServiceError
from services import chatgpt_structured as mod


@pytest.fixture(autouse=True)
def reset_caches():
    for name in ("_load_instructions", "_load_schema", "_get_openai_client"):
        func = getattr(mod, name)
        cache_clear = getattr(func, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()
    yield
    for name in ("_load_instructions", "_load_schema", "_get_openai_client"):
        func = getattr(mod, name)
        cache_clear = getattr(func, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


def _build_payload():
    return {
        "objects": [
            {
                "object_rent_vat": None,
                "object_name": None,
                "sale_price_per_building": None,
                "object_use_type": None,
                "buildings": [
                    {
                        "building_name": None,
                        "listings": [
                            {
                                "use_type": None,
                                "area_sqm": None,
                                "divisible_from_sqm": None,
                                "floor": None,
                                "market_type": None,
                                "fitout_condition": None,
                                "delivery_date": None,
                                "assignment_of_rights": None,
                                "assignment_details": None,
                                "rent_rate": None,
                                "rent_cost_month_per_room": None,
                                "rent_vat": None,
                                "sale_price_per_sqm": None,
                                "sale_vat": None,
                                "opex_included": None,
                                "opex_year_per_sqm": None,
                            }
                        ],
                    }
                ],
            }
        ]
    }


def test_extract_structured_objects_parses_openai_response(monkeypatch):
    payload = _build_payload()

    def fake_create(**kwargs):  # noqa: ANN001
        tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(payload)))
        message = SimpleNamespace(tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    dummy_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
    )

    monkeypatch.setattr(mod, "_get_openai_client", lambda: dummy_client)

    result = mod.extract_structured_objects("some text")
    assert result == payload


def test_extract_structured_objects_requires_text():
    with pytest.raises(ServiceError):
        mod.extract_structured_objects("")
