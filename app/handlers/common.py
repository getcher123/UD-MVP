"""Common command handlers: /start and /help."""

from aiogram import Router, types
from aiogram.filters import Command, CommandStart


router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """Handle /start command."""
    await message.answer(
        "Пришлите файл (PDF/DOCX/PPTX/XLSX/JPG/PNG) до 20 МБ — верну Excel"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """Handle /help command."""
    await message.answer(
        "Поддерживаемые форматы: PDF, DOCX, PPTX, XLSX, JPG, PNG.\n"
        "Ограничения: размер до 20 МБ. Отправьте один файл сообщением."
    )

