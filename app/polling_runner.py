"""Local polling runner for aiogram 3.x.

Run from project root:

    python -m app.polling_runner

This runner reuses the same routers as the webhook app
and starts long-polling for local development.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from .config import settings
from .handlers.common import router as common_router
from .handlers.documents import router as documents_router


async def main() -> None:
    # Basic console logging suitable for local debugging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(settings.bot_token)
    dp = Dispatcher()

    # Register routers
    dp.include_router(common_router)
    dp.include_router(documents_router)

    # Start polling with only the updates we actually handle
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

