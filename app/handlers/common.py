"""Common command handlers: /start, /help, /health."""

import json

import httpx
from aiogram import Router, types
from aiogram.filters import Command, CommandStart

from ..services.ms_client import get_health


router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """Handle /start command."""
    await message.answer("Просто добавьте файл (PDF/DOCX/PPTX/XLSX/JPG/PNG) до 20 МБ — получите Excel")


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """Handle /help command."""
    await message.answer(
        "Поддерживаемые форматы: PDF, DOCX, PPTX, XLSX, JPG, PNG.\n"
        "Лимит размера: до 20 МБ. После обработки выдаем итоговый файл."
    )


@router.message(Command("health"))
async def cmd_health(message: types.Message) -> None:
    """Check microservice health endpoint and report status."""

    try:
        payload = await get_health()
    except httpx.HTTPStatusError as exc:
        await message.answer(
            f"Микросервис ответил ошибкой: {exc.response.status_code} {exc.response.reason_phrase}"
        )
        return
    except httpx.HTTPError as exc:
        await message.answer(f"Не удалось подключиться к микросервису: {exc}")
        return
    except Exception as exc:
        await message.answer(f"Неожиданная ошибка при проверке микросервиса: {exc}")
        return

    status = payload.get("status")
    if status is None and "ok" in payload:
        status = "ok" if payload["ok"] else "not ok"
    if status is None:
        status = "unknown"

    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    await message.answer(f"Микросервис доступен (status: {status})\n`\n{pretty}\n`")

