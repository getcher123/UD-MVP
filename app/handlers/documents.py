"""Document message handlers."""

from aiogram import Router, types, F

router = Router()


@router.message(F.document)
async def handle_document(message: types.Message) -> None:
    """Handle incoming document messages."""
    await message.answer("Document received")
