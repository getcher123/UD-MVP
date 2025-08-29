"""Handlers for incoming documents and photos."""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Router, types, F
from aiogram.types import BufferedInputFile

from ..utils.files import safe_filename, max_size_bytes
from ..services.ms_client import process_file


router = Router()


def _uploads_dir() -> Path:
    # app/handlers -> app -> repo root
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "uploads"


async def _reject_audio_if_any(message: types.Message) -> bool:
    """Return True if audio/voice present and reply with hint."""
    if getattr(message, "audio", None) is not None or getattr(message, "voice", None) is not None:
        await message.answer("Аудио пока не поддерживается")
        return True
    return False


@router.message(F.document)
async def on_document(message: types.Message) -> None:
    """Handle incoming document messages (PDF/DOCX/PPTX/XLSX/etc)."""
    if await _reject_audio_if_any(message):
        return

    doc = message.document
    if doc is None:
        return

    # Reject audio-like documents as unsupported
    mime = (doc.mime_type or "").lower()
    if mime.startswith("audio/"):
        await message.answer("Аудио пока не поддерживается")
        return

    size_limit = max_size_bytes()
    if (doc.file_size or 0) > size_limit:
        await message.answer(f"Файл слишком большой. Максимум {size_limit // (1024*1024)} МБ")
        return

    # Prepare destination path
    filename = safe_filename(doc.file_name or f"document_{doc.file_unique_id}")
    dest = _uploads_dir() / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Download file to disk
    await message.bot.download(doc, destination=dest)

    await message.answer("Файл получен, обрабатываю…")

    try:
        xlsx_bytes, out_name = await process_file(dest, str(message.chat.id))
        buf = BufferedInputFile(xlsx_bytes, filename=out_name)
        await message.answer_document(document=buf, caption="✅ Готово: сводная таблица")
    except Exception:  # keep bot stable on processing errors
        logging.exception("Processing failed for %s", dest)
    finally:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            logging.exception("Failed to remove %s", dest)


@router.message(F.photo)
async def on_photo(message: types.Message) -> None:
    """Handle incoming photo messages (pick the largest size)."""
    if await _reject_audio_if_any(message):
        return

    if not message.photo:
        return

    photo = message.photo[-1]

    size_limit = max_size_bytes()
    if (photo.file_size or 0) > size_limit:
        await message.answer(f"Файл слишком большой. Максимум {size_limit // (1024*1024)} МБ")
        return

    filename = safe_filename(f"photo_{photo.file_unique_id}.jpg")
    dest = _uploads_dir() / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    await message.bot.download(photo, destination=dest)

    await message.answer("Файл получен, обрабатываю…")

    try:
        xlsx_bytes, out_name = await process_file(dest, str(message.chat.id))
        buf = BufferedInputFile(xlsx_bytes, filename=out_name)
        await message.answer_document(document=buf, caption="✅ Готово: сводная таблица")
    except Exception:
        logging.exception("Processing failed for %s", dest)
    finally:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            logging.exception("Failed to remove %s", dest)


@router.message(F.audio)
async def on_audio(message: types.Message) -> None:
    """Explicit handler for audio messages (e.g., MP3)."""
    await message.answer("Аудио пока не поддерживается")


@router.message(F.voice)
async def on_voice(message: types.Message) -> None:
    """Explicit handler for voice messages (Opus in OGG)."""
    await message.answer("Аудио пока не поддерживается")
