"""Document message handlers."""

from aiogram import Router, types

router = Router()


@router.message(content_types=types.ContentType.DOCUMENT)
async def handle_document(message: types.Message) -> None:
    """Handle incoming document messages."""
    await message.answer("Document received")
