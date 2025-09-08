"""Webhook-based application entry point using FastAPI."""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from .config import settings
from .utils.files import ensure_dirs
from .handlers.common import router as common_router
from .handlers.documents import router as documents_router


# --- Bot & Dispatcher setup ---
bot = Bot(settings.bot_token)
dp = Dispatcher()

# Include routers with commands and other handlers
dp.include_router(common_router)
dp.include_router(documents_router)


# --- FastAPI app (lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    ensure_dirs()
    webhook_url = getattr(settings, "webhook_url", "")
    if webhook_url:
        allowed = dp.resolve_used_update_types()
        await bot.set_webhook(webhook_url, allowed_updates=allowed)
        logging.info("Webhook set: %s (allowed_updates=%s)", webhook_url, allowed)
    else:
        logging.info("Webhook URL not set; app will still accept /webhook but Telegram won't call it")
    try:
        yield
    finally:
        # Shutdown
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logging.info("Webhook deleted (shutdown)")
        finally:
            await bot.session.close()


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Simple liveness probe endpoint."""
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Receive Telegram updates and dispatch them to aiogram."""
    body = await request.body()
    try:
        update = Update.model_validate_json(body)
    except Exception:
        # Fallback in case content-type handling differs
        payload: Any = await request.json()
        update = Update.model_validate(payload)

    # Process update asynchronously to avoid Telegram read timeouts
    asyncio.create_task(dp.feed_update(bot, update))
    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn

    # Run with app instance to avoid re-importing module
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        reload=bool(os.getenv("RELOAD", "0") == "1"),
    )
