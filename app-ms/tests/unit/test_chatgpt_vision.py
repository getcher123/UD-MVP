import sys
from pathlib import Path
from types import SimpleNamespace
import base64
import json

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

import pytest

from core.errors import ServiceError
from services import chatgpt_structured as structured
from services import chatgpt_vision as mod


@pytest.fixture(autouse=True)
def reset_caches():
    for func in (structured._load_instructions, structured._get_openai_client):
        cache_clear = getattr(func, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()
    yield
    for func in (structured._load_instructions, structured._get_openai_client):
        cache_clear = getattr(func, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


def test_analyze_page_image_missing_file():
    with pytest.raises(ServiceError):
        mod.analyze_page_image("nonexistent.png")


def test_analyze_page_image_success(monkeypatch, tmp_path):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("vision", encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{\"type\": \"object\", \"additionalProperties\": true}", encoding="utf-8")

    image_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQYV2NgYGAAAAAEAAGjCh0AAAAASUVORK5CYII=")
    image_path = tmp_path / "page.png"
    image_path.write_bytes(image_bytes)

    payload = {"page_index": 2, "text": "пример"}

    def fake_create(model, messages, tools, tool_choice):  # noqa: ANN001
        assert model == "vision-test"
        assert tools[0]["function"]["name"] == "emit_page"
        envelope = json.dumps({"result": json.dumps(payload, ensure_ascii=False)})
        tool_call = SimpleNamespace(function=SimpleNamespace(arguments=envelope))
        message = SimpleNamespace(tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    dummy_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    class DummySettings:
        PDF_VISION_PROMPT_PATH = str(prompt_path)
        PDF_VISION_SCHEMA_PATH = str(schema_path)
        OPENAI_VISION_MODEL = "vision-test"
        OPENAI_API_KEY = "sk-test"

    monkeypatch.setattr(mod, "_get_openai_client", lambda: dummy_client)
    monkeypatch.setattr(mod, "get_settings", lambda: DummySettings())

    result = mod.analyze_page_image(str(image_path))
    assert result == payload


def test_analyze_page_image_invalid_json(monkeypatch, tmp_path):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("vision", encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{\"type\": \"object\", \"additionalProperties\": true}", encoding="utf-8")
    image_path = tmp_path / "page.png"
    image_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQYV2NgYGAAAAAEAAGjCh0AAAAASUVORK5CYII="))

    def fake_create(model, messages, tools, tool_choice):  # noqa: ANN001
        envelope = json.dumps({"result": "not json"})
        tool_call = SimpleNamespace(function=SimpleNamespace(arguments=envelope))
        message = SimpleNamespace(tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    dummy_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    class DummySettings:
        PDF_VISION_PROMPT_PATH = str(prompt_path)
        PDF_VISION_SCHEMA_PATH = str(schema_path)
        OPENAI_VISION_MODEL = "vision-test"
        OPENAI_API_KEY = "sk-test"

    monkeypatch.setattr(mod, "_get_openai_client", lambda: dummy_client)
    monkeypatch.setattr(mod, "get_settings", lambda: DummySettings())

    with pytest.raises(ServiceError):
        mod.analyze_page_image(str(image_path))
