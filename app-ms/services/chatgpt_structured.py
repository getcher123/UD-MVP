from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

from core.config import get_settings
from core.errors import ErrorCode, ServiceError


@lru_cache(maxsize=1)
def _load_instructions(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError as exc:  # pragma: no cover - configuration errors
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Instructions file not found: {path}") from exc
    except Exception as exc:  # noqa: BLE001 - propagate as service error
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Failed to read instructions: {exc}") from exc


@lru_cache(maxsize=1)
def _load_schema(path: str) -> Dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:  # pragma: no cover - configuration errors
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Schema file not found: {path}") from exc
    except Exception as exc:  # noqa: BLE001 - propagate as service error
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Failed to read schema: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Invalid schema JSON: {exc}") from exc


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, "OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def extract_structured_objects(raw_text: str) -> Dict[str, Any]:
    if not raw_text or not raw_text.strip():
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 422, "raw_text must be provided")

    settings = get_settings()
    instructions = _load_instructions(settings.CHATGPT_INSTRUCTIONS_PATH)
    schema = _load_schema(settings.CHATGPT_SCHEMA_PATH)
    client = _get_openai_client()

    tool_spec = {
        "type": "function",
        "function": {
            "name": "emit_objects",
            "description": "Верни данные строго по целевой схеме.",
            "strict": True,
            "parameters": schema,
        },
    }

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": f"Извлеки поля из текста:\n{raw_text}"},
            ],
            tools=[tool_spec],
            tool_choice={"type": "function", "function": {"name": "emit_objects"}},
        )
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(ErrorCode.OPENAI_ERROR, 424, f"OpenAI request failed: {exc}") from exc

    try:
        tool_call = response.choices[0].message.tool_calls[0]
        arguments = tool_call.function.arguments
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(ErrorCode.OPENAI_ERROR, 500, f"Malformed OpenAI response: {exc}") from exc

    try:
        return json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ServiceError(ErrorCode.OPENAI_ERROR, 500, f"Invalid JSON payload from OpenAI: {exc}") from exc


__all__ = ["extract_structured_objects"]
