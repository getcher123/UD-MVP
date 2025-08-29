"""Main application entry point."""

from aiogram import Bot, Dispatcher, types

from .config import settings


def create_dispatcher() -> Dispatcher:
    """Create and return a configured dispatcher."""
    bot = Bot(settings.bot_token)
    dp = Dispatcher()

    @dp.message()
    async def start(message: types.Message) -> None:
        await message.answer("Hello!")

    return dp


async def main() -> None:
    """Run bot polling."""
    dp = create_dispatcher()
    await dp.start_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
