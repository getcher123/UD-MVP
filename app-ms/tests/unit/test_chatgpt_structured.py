import json
import sys
from pathlib import Path
from types import SimpleNamespace

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))


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


def _write_config_files(tmp_path):
    instructions_path = tmp_path / "instructions.txt"
    instructions_path.write_text("system instructions", encoding="utf-8")

    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "properties": {
            "objects": {"type": "array"}
        },
        "required": ["objects"],
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return instructions_path, schema_path


class DummySettings:
    def __init__(self, instructions_path, schema_path):
        self.OPENAI_API_KEY = "sk-test"
        self.OPENAI_MODEL = "gpt-test"
        self.CHATGPT_INSTRUCTIONS_PATH = str(instructions_path)
        self.CHATGPT_SCHEMA_PATH = str(schema_path)


def test_extract_structured_objects_parses_openai_response(monkeypatch, tmp_path):
    instructions_path, schema_path = _write_config_files(tmp_path)
    payload = {
        "objects": [
            {
                "object_rent_vat": None,
                "object_name": None,
                "sale_price_per_building": None,
                "object_use_type": None,
                "buildings": [],
            }
        ]
    }

    def fake_create(model, messages, tools, tool_choice):  # noqa: ANN001
        assert model == "gpt-test"
        assert any("Извлеки поля" in msg["content"] for msg in messages if isinstance(msg, dict))
        tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(payload)))
        message = SimpleNamespace(tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    dummy_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
    )

    monkeypatch.setattr(mod, "_get_openai_client", lambda: dummy_client)
    monkeypatch.setattr(mod, "get_settings", lambda: DummySettings(instructions_path, schema_path))

    result = mod.extract_structured_objects("какой-то текст")
    assert result == payload


def test_extract_structured_objects_requires_text():
    with pytest.raises(ServiceError):
        mod.extract_structured_objects("")
