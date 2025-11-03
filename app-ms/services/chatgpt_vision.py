from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict

from core.config import get_settings
from core.errors import ErrorCode, ServiceError
from services.chatgpt_structured import _get_openai_client, _load_instructions, _load_schema

logger = logging.getLogger("service.chatgpt_vision")


_SUPPORTED_SUFFIX_TO_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def _detect_mime(path: Path) -> str:
    suffix = path.suffix.lstrip(".").lower()
    mime = _SUPPORTED_SUFFIX_TO_MIME.get(suffix)
    if not mime:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, f"Unsupported image format: {path.suffix}")
    return mime


def analyze_page_image(image_path: str, *, prompt_path: str | None = None, model: str | None = None) -> Dict[str, Any]:
    """Send a single page image to OpenAI vision model and return parsed JSON."""
    image_file = Path(image_path)
    if not image_file.exists() or not image_file.is_file():
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, f"Image not found: {image_path}")

    mime = _detect_mime(image_file)
    settings = get_settings()
    prompt_file = prompt_path or settings.PDF_VISION_PROMPT_PATH
    prompt = _load_instructions(prompt_file)
    schema = _load_schema(settings.PDF_VISION_SCHEMA_PATH)

    start_ts = time.perf_counter()
    logger.info("vision.start", extra={"image": str(image_file)})

    tool_spec = {
        "type": "function",
        "function": {
            "name": "emit_page",
            "description": "Верни распознанную страницу строго по целевой схеме.",
            "strict": True,
            "parameters": schema,
        },
    }

    try:
        data = image_file.read_bytes()
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Failed to read image: {exc}") from exc

    encoded = base64.b64encode(data).decode("ascii")
    client = _get_openai_client()

    try:
        response = client.chat.completions.create(
            model=model or settings.OPENAI_VISION_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Изучи страницу и верни JSON строго по функции emit_page."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                    ],
                },
            ],
            tools=[tool_spec],
            tool_choice={"type": "function", "function": {"name": "emit_page"}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI vision request failed", extra={"image": str(image_file)})
        raise ServiceError(ErrorCode.OPENAI_ERROR, 424, f"OpenAI vision request failed: {exc}") from exc

    try:
        message = response.choices[0].message
        tool_call = message.tool_calls[0]
        arguments = tool_call.function.arguments
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(ErrorCode.OPENAI_ERROR, 500, f"Malformed response from OpenAI: {exc}") from exc

    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:  # noqa: BLE001
        raise ServiceError(ErrorCode.OPENAI_ERROR, 500, f"OpenAI vision produced invalid JSON envelope: {exc}: {arguments[:200]}") from exc

    page_payload: dict[str, Any] | None = None
    if isinstance(parsed, dict):
        if "result" in parsed and isinstance(parsed["result"], str):
            result_text = parsed["result"]
            if not result_text.strip():
                raise ServiceError(ErrorCode.OPENAI_ERROR, 500, "OpenAI vision payload missing result string")
            try:
                page_payload = json.loads(result_text)
            except json.JSONDecodeError as exc:
                raise ServiceError(ErrorCode.OPENAI_ERROR, 500, f"OpenAI vision produced invalid JSON: {exc}: {result_text[:200]}") from exc
        else:
            page_payload = parsed
    elif isinstance(parsed, str):
        try:
            page_payload = json.loads(parsed)
        except json.JSONDecodeError as exc:
            raise ServiceError(ErrorCode.OPENAI_ERROR, 500, f"OpenAI vision produced invalid JSON: {exc}: {parsed[:200]}") from exc
    else:
        raise ServiceError(ErrorCode.OPENAI_ERROR, 500, "OpenAI vision returned unsupported payload format")

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    blocks_count = len(page_payload.get("blocks", [])) if isinstance(page_payload, dict) else None
    logger.info("vision.done", extra={"image": str(image_file), "elapsed_ms": elapsed_ms, "blocks": blocks_count})

    return page_payload


__all__ = ["analyze_page_image"]
