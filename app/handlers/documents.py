"""Handlers for incoming documents, photos, and audio."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from aiogram import Router, types, F
from aiogram.types import BufferedInputFile, TelegramObject
import httpx

from ..utils.files import safe_filename, max_size_bytes
from ..services.ms_client import process_file


router = Router()
logger = logging.getLogger(__name__)


def _uploads_dir() -> Path:
    # app/handlers -> app -> repo root
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "uploads"


def _guess_extension(mime_type: Optional[str], default_suffix: str) -> str:
    if default_suffix and not default_suffix.startswith("."):
        default_suffix = f".{default_suffix}"
    default_suffix = default_suffix.lower()
    if not mime_type:
        return default_suffix

    mime = mime_type.split(";")[0].strip().lower()
    mapping = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/ogg": ".ogg",
        "audio/opus": ".ogg",
        "audio/x-opus+ogg": ".ogg",
        "audio/webm": ".webm",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/aac": ".aac",
        "audio/flac": ".flac",
    }
    if mime in mapping:
        return mapping[mime]

    subtype = mime.split("/")[-1]
    if not subtype:
        return default_suffix
    if subtype == "mpeg":
        return ".mp3"
    return f".{subtype}"


def _fallback_filename(
    prefix: str,
    unique_id: Optional[str],
    mime_type: Optional[str],
    default_suffix: str,
) -> str:
    suffix = _guess_extension(mime_type, default_suffix)
    uid = unique_id or "file"
    return f"{prefix}_{uid}{suffix}" if suffix else f"{prefix}_{uid}"


async def _process_telegram_file(
    message: types.Message,
    telegram_file: TelegramObject,
    *,
    preferred_name: Optional[str],
    fallback_prefix: str,
    default_suffix: str,
    file_size: Optional[int],
    mime_type: Optional[str],
    log_kind: str,
) -> None:
    size_limit = max_size_bytes()
    if file_size and file_size > size_limit:
        await message.answer("Файл слишком большой (максимум 20 МБ)")
        return

    filename = preferred_name or _fallback_filename(
        fallback_prefix,
        getattr(telegram_file, "file_unique_id", None),
        mime_type,
        default_suffix,
    )
    safe_name = safe_filename(filename)

    if not Path(safe_name).suffix:
        suffix = _guess_extension(mime_type, default_suffix)
        if suffix:
            safe_name = safe_filename(f"{safe_name}{suffix}")

    dest = _uploads_dir() / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "[documents] Получен %s: chat_id=%s name=%s size=%sB",
        log_kind,
        getattr(message.chat, "id", "?"),
        safe_name,
        file_size,
    )
    await message.bot.download(telegram_file, destination=dest)

    await message.answer("Файл получен, обрабатываю…")

    try:
        logger.info("[documents] Отправляю файл в МС: path=%s kind=%s", dest, log_kind)
        xlsx_bytes, out_name, status_messages = await process_file(dest, str(message.chat.id))
        logger.info(
            "[documents] Получена сводная таблица от МС: out_name=%s size=%sB kind=%s",
            out_name,
            len(xlsx_bytes),
            log_kind,
        )
        buf = BufferedInputFile(xlsx_bytes, filename=out_name)
        await message.answer_document(document=buf, caption="✅ Готово: сводная таблица")
        for status in status_messages or []:
            text = status.get("message") if isinstance(status, dict) else None
            if text:
                await message.answer(text)
    except httpx.HTTPStatusError as exc:
        logger.exception(
            "[documents] Ошибка от микросервиса %s для %s",
            getattr(exc.response, "status_code", "?"),
            dest,
        )
        await message.answer("Не удалось обработать файл, попробуйте позже")
    except httpx.HTTPError:
        logger.exception("[documents] Сетевая ошибка при работе с МС для %s", dest)
        await message.answer("Не удалось обработать файл, попробуйте позже")
    except Exception:
        logger.exception("[documents] Непредвиденная ошибка обработки файла %s", dest)
        await message.answer("Не удалось обработать файл, попробуйте позже")
    finally:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            logger.exception("[documents] Не удалось удалить временный файл %s", dest)


@router.message(F.document)
async def on_document(message: types.Message) -> None:
    """Handle incoming document messages (PDF/DOCX/PPTX/XLSX/etc)."""
    doc = message.document
    if doc is None:
        return

    await _process_telegram_file(
        message,
        doc,
        preferred_name=doc.file_name,
        fallback_prefix="document",
        default_suffix="",
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        log_kind="document",
    )


@router.message(F.photo)
async def on_photo(message: types.Message) -> None:
    """Handle incoming photo messages (pick the largest size)."""
    if not message.photo:
        return

    photo = message.photo[-1]

    await _process_telegram_file(
        message,
        photo,
        preferred_name=f"photo_{photo.file_unique_id}.jpg",
        fallback_prefix="photo",
        default_suffix=".jpg",
        file_size=photo.file_size,
        mime_type="image/jpeg",
        log_kind="photo",
    )


@router.message(F.audio)
async def on_audio(message: types.Message) -> None:
    """Process audio messages (e.g., MP3/M4A/OGG)."""
    audio = message.audio
    if audio is None:
        return

    await _process_telegram_file(
        message,
        audio,
        preferred_name=audio.file_name,
        fallback_prefix="audio",
        default_suffix=".mp3",
        file_size=audio.file_size,
        mime_type=audio.mime_type,
        log_kind="audio",
    )


@router.message(F.voice)
async def on_voice(message: types.Message) -> None:
    """Process voice messages (Opus in OGG)."""
    voice = message.voice
    if voice is None:
        return

    await _process_telegram_file(
        message,
        voice,
        preferred_name=None,
        fallback_prefix="voice",
        default_suffix=".ogg",
        file_size=voice.file_size,
        mime_type=voice.mime_type,
        log_kind="voice",
    )
